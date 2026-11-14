import type { DatasetPanel } from '../services/dataset'
export type Decimal = string | null
export interface Source { file: string; row: number; value_column: string }
export interface Envelope { study_id: string; provenance: string; note: string }
export interface CrewList extends Envelope { astronauts: {crew_id: string; visits: string[]}[] }
export interface PanelList extends Envelope { panels: {panel: DatasetPanel; group: string; biomarkers: {biomarker: string; unit: string}[]}[] }
export interface Measurement { crew_id: string; panel: string; biomarker: string; visit: string; value: Decimal; value_status: string; unit: string; lab_ref_min: Decimal; lab_ref_max: Decimal; source: Source; provenance: string }
export interface Analysis { crew_id: string; panel: string; biomarker: string; visit: string; current_value: Decimal; current_value_status: string; unit: string; baseline_value: Decimal; baseline_status: string; baseline_sample_count: number; absolute_change: Decimal; percentage_change: Decimal; change_direction: string; lab_comparison: string; lab_ref_min: Decimal; lab_ref_max: Decimal; source: Source; provenance: string; analysis_notes: string[] }
export interface TrajectoryVisit { visit: string; phase_day: number; value: Decimal; value_status: string; change_from_baseline: Decimal; distance_from_baseline: Decimal; distance_movement: string | null; lab_comparison: string; source: Source }
export interface Trajectory { crew_id: string; panel: string; biomarker: string; unit: string; baseline_value: Decimal; baseline_status: string; baseline_sample_count: number; trajectory_classification: string; visits: TrajectoryVisit[]; finding: string; evidence_limitations: string[]; provenance: string }
export interface History extends Envelope { measurements: Measurement[] }
export interface Postflight extends Envelope { results: Analysis[] }
export interface TrajectoryResponse extends Envelope { classification_note: string; trajectory: Trajectory }
export interface Comparison extends Envelope { classification_note: string; trajectories: Trajectory[] }
