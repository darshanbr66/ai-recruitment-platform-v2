/** Mirrors backend/app/schemas/public_campus_drive.py. */

import type { CampusDriveStatus } from "./campusDrive";

export interface PublicCampusDriveView {
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
