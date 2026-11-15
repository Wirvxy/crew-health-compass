import * as THREE from 'three'

export const HEALTH_COLORS = { normal: '#43d9a3', watch: '#ffbc55', action: '#ff5c6c', unavailable: '#9bb0bf' } as const
export type HealthTone = keyof typeof HEALTH_COLORS
export type HealthLocation = 'head' | 'chest' | 'lungs'
export interface HealthSignal {
  id: string; label: string; value: string; message: string; tone: HealthTone; location: HealthLocation
}
export interface HealthZone { location: HealthLocation; tone: HealthTone; signals: HealthSignal[] }
const PRIORITY: Record<HealthTone, number> = { unavailable: 0, normal: 1, watch: 2, action: 3 }
export function healthZones(signals: HealthSignal[]): HealthZone[] {
  const zones: HealthZone[] = []
  for (const signal of signals) {
    const zone = zones.find(item => item.location === signal.location)
    if (!zone) zones.push({ location: signal.location, tone: signal.tone, signals: [signal] })
    else {
      zone.signals.push(signal)
      if (PRIORITY[signal.tone] > PRIORITY[zone.tone]) zone.tone = signal.tone
    }
  }
  const order: HealthLocation[] = ['head', 'chest', 'lungs']
  return zones.sort((a, b) => order.indexOf(a.location) - order.indexOf(b.location))
}

const REGIONS: Record<HealthLocation, { bone: string; centers: number[][]; radius: number[]; side: number }> = {
  head: { bone: 'spine006', centers: [[0, 1.05, .02]], radius: [.26, .3, .24], side: 1 },
  chest: { bone: 'spine004', centers: [[.02, .62, .23]], radius: [.17, .2, .17], side: -1 },
  lungs: { bone: 'spine004', centers: [[-.19, .68, .13], [.19, .68, .13]], radius: [.13, .22, .17], side: 1 },
}
interface RegionEffect { root: THREE.Group; shells: THREE.Mesh[]; zone: HealthZone }
type LitMaterial = THREE.MeshPhongMaterial | THREE.MeshStandardMaterial

/** Bone-bound effects and world-space emissive masks share the same moving anchors. */
export class AstronautHealth {
  private effects: RegionEffect[] = []
  private uniforms = {
    healthCount: { value: 0 },
    healthInverse: { value: Array.from({ length: 4 }, () => new THREE.Matrix4()) },
    healthColor: { value: Array.from({ length: 4 }, () => new THREE.Color()) },
  }

  constructor(private model: THREE.Group, private pivot: THREE.Group) {
    model.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return
      const materials = Array.isArray(object.material) ? object.material : [object.material]
      for (const original of materials) {
        if (!('emissive' in original)) continue
        const material = original as LitMaterial
        material.onBeforeCompile = shader => {
          Object.assign(shader.uniforms, this.uniforms)
          shader.vertexShader = 'varying vec3 healthWorldPosition;\n' + shader.vertexShader
          shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', '#include <project_vertex>\nhealthWorldPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;')
          shader.fragmentShader = 'varying vec3 healthWorldPosition;\nuniform int healthCount;\nuniform mat4 healthInverse[4];\nuniform vec3 healthColor[4];\n' + shader.fragmentShader
          shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
            for (int i = 0; i < 4; i++) {
              if (i >= healthCount) break;
              vec3 region = (healthInverse[i] * vec4(healthWorldPosition, 1.0)).xyz;
              float mask = exp(-dot(region, region) * 2.4);
              totalEmissiveRadiance += healthColor[i] * mask * 0.35;
              diffuseColor.rgb = mix(diffuseColor.rgb, healthColor[i], mask * 0.65);
            }`)
        }
        material.customProgramCacheKey = () => 'crew-health-emission-v1'
        material.needsUpdate = true
      }
    })
  }

  setZones(zones: HealthZone[]) {
    this.clear()
    this.pivot.updateWorldMatrix(true, true)
    for (const zone of zones) {
      const region = REGIONS[zone.location]
      const bone = this.model.getObjectByName(region.bone) ?? this.model
      const root = new THREE.Group()
      const world = this.pivot.localToWorld(new THREE.Vector3(...region.centers[0]))
      root.position.copy(bone.worldToLocal(world))
      root.quaternion.copy(bone.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(this.pivot.getWorldQuaternion(new THREE.Quaternion())))
      const scale = bone.getWorldScale(new THREE.Vector3())
      root.scale.set(1 / scale.x, 1 / scale.y, 1 / scale.z)
      bone.add(root)
      root.updateWorldMatrix(true, true)
      const shells = region.centers.map(center => {
        const material = new THREE.ShaderMaterial({
          uniforms: { color: { value: new THREE.Color(HEALTH_COLORS[zone.tone]) } },
          vertexShader: `varying vec3 viewNormal; varying vec3 viewDirection;
            void main() {
              vec4 p = modelViewMatrix * vec4(position, 1.0);
              viewNormal = normalize(normalMatrix * normal); viewDirection = -p.xyz;
              gl_Position = projectionMatrix * p;
            }`,
          fragmentShader: `uniform vec3 color; varying vec3 viewNormal; varying vec3 viewDirection;
            void main() {
              float facing = abs(dot(normalize(viewNormal), normalize(viewDirection)));
              gl_FragColor = vec4(color, pow(facing, 1.6) * 0.48);
              #include <tonemapping_fragment>
              #include <colorspace_fragment>
            }`,
          transparent: true, depthWrite: false, depthTest: false,
        })
        const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 24), material)
        shell.position.copy(root.worldToLocal(this.pivot.localToWorld(new THREE.Vector3(...center))))
        shell.scale.fromArray(region.radius)
        root.add(shell)
        return shell
      })
      this.effects.push({ root, shells, zone })
    }
  }

  /** Run after matrix updates so masks, leader lines and auras stay aligned during rotation. */
  update(camera: THREE.Camera, width: number, height: number, boxes: Map<string, HTMLDivElement>, lines: Map<string, SVGPolylineElement>) {
    let index = 0
    const rightRows = this.effects.filter(effect => REGIONS[effect.zone.location].side > 0)
    for (const effect of this.effects) {
      for (const shell of effect.shells) {
        this.uniforms.healthInverse.value[index].copy(shell.matrixWorld).invert()
        this.uniforms.healthColor.value[index].set(HEALTH_COLORS[effect.zone.tone])
        index++
      }
      const box = boxes.get(effect.zone.location), line = lines.get(effect.zone.location)
      if (!box || !line || width === 0 || height === 0) continue
      const point = effect.root.getWorldPosition(new THREE.Vector3()).project(camera)
      const x = (point.x + 1) * width / 2, y = (1 - point.y) * height / 2
      const left = REGIONS[effect.zone.location].side < 0
      const row = left ? 0 : rightRows.indexOf(effect)
      const labelX = left ? 10 : width - box.offsetWidth - 10
      const previous = rightRows[row - 1]
      const previousHeight = previous ? (boxes.get(previous.zone.location)?.offsetHeight ?? 130) : 0
      const labelY = width <= 600
        ? height + 12 + (row > 0 ? previousHeight + 12 : 0)
        : Math.min(height - box.offsetHeight - 12, Math.max(44, y - 120 + row * 145))
      box.style.transform = `translate(${labelX}px, ${labelY}px)`
      const endX = left ? labelX + box.offsetWidth : labelX
      const endY = labelY + 22
      line.setAttribute('points', `${x},${y} ${endX + (left ? 20 : -20)},${endY} ${endX},${endY}`)
      const visible = point.z >= -1 && point.z <= 1
      box.hidden = !visible
      line.style.visibility = visible ? 'visible' : 'hidden'
      line.dataset.anchorX = String(x)
      line.dataset.anchorY = String(y)
    }
    this.uniforms.healthCount.value = index
  }

  private clear() {
    for (const effect of this.effects) {
      effect.root.removeFromParent()
      for (const shell of effect.shells) {
        shell.geometry.dispose()
        const material = shell.material as THREE.Material
        material.dispose()
      }
    }
    this.effects = []
    this.uniforms.healthCount.value = 0
  }
  dispose() { this.clear() }
  hit(ray: THREE.Raycaster) {
    return this.effects.find(effect => ray.intersectObjects(effect.shells).length)?.zone.signals[0]?.id
  }
}
