/** Mirrors backend/app/schemas/public_campus_drive.py. */

import type { CampusDriveStatus } from "./campusDrive";

export interface PublicCampusDriveView {
  kind: "drive";
  name: string;
  college_name: string;
  description: string | null;
  job_title: string;
  job_description: string;
  organization_name: string;
  registration_deadline: string | null;
  status: CampusDriveStatus;
  has_assessment: boolean;
}

/** Returned once a drive is CLOSED — deliberately carries no JD, drive
 * description, or assessment info (SIGVITAS platform overhaul § 16). */
export interface PublicCampusDriveUnavailable {
  kind: "unavailable";
  message: string;
}

export type PublicCampusDriveResult = PublicCampusDriveView | PublicCampusDriveUnavailable;

export interface PublicCampusDriveApplicationResult {
  application_id: string;
  job_title: string;
  candidate_email: string;
  status: string;
  assessment_invitation_link: string | null;
}

export interface CampusDriveApplicationFormValues {
  full_name: string;
  email: string;
  phone: string;
}
