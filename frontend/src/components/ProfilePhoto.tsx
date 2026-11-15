import commander from '../assets/profiles/commander.jpg'
import flightEngineer1 from '../assets/profiles/flight_engineer_1.jpg'
import flightEngineer2 from '../assets/profiles/flight_engineer_2.jpg'
import flightEngineer3 from '../assets/profiles/flight_engineer_3.jpg'

// One decorative picture per crew profile (helmeted, no faces). Source and licence are not documented yet: see NOTICE.
// `focus` keeps the helmet in view when the picture is cropped to a square or a circle.
const PHOTOS: Record<string, { src: string; focus: string }> = {
  commander: { src: commander, focus: 'center 30%' },
  flight_engineer_1: { src: flightEngineer1, focus: 'center 35%' },
  flight_engineer_2: { src: flightEngineer2, focus: 'center 30%' },
  flight_engineer_3: { src: flightEngineer3, focus: 'center 60%' },
}

/** The profile's picture, or nothing for a profile without one (the caller then shows its fallback). */
export default function ProfilePhoto({ id, className }: { id: string; className: string }) {
  const photo = PHOTOS[id]
  if (!photo) return null
  return <img className={className} src={photo.src} alt="" decoding="async" style={{ objectPosition: photo.focus }} />
}
export const hasProfilePhoto = (id: string) => id in PHOTOS
