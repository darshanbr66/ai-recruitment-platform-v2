import { Link } from "react-router-dom";
import { Icon } from "../../shared/components/Icon";
import type { SigviJobCard as JobCard } from "../../types/sigvi";

/** A compact pointer to one public role — enough to decide, then hand off to
 * the real careers page (it does not duplicate it). Every field is one the
 * anonymous careers page already shows. */
export function SigviJobCard({ job, onNavigate }: { job: JobCard; onNavigate: () => void }) {
  return (
    <article className="sigvi-job" aria-label={`Role: ${job.title}`}>
      <h3 className="sigvi-job-title">{job.title}</h3>
      <div className="sigvi-job-meta">
        {job.department && <span className="chip">{job.department}</span>}
        {job.location && (
          <span className="chip">
            <Icon name="pin" size={12} />
            {job.location}
          </span>
        )}
        {job.employment_type && <span className="chip">{job.employment_type}</span>}
      </div>
      {job.summary && <p className="sigvi-job-summary">{job.summary}</p>}
      <div className="sigvi-job-actions">
        <Link to={job.view_path} className="btn btn-ghost btn-sm" onClick={onNavigate}>
          View job
        </Link>
        <Link to={job.apply_path} className="btn btn-primary btn-sm" onClick={onNavigate}>
          Apply
          <Icon name="arrow-right" size={14} />
        </Link>
      </div>
    </article>
  );
}
