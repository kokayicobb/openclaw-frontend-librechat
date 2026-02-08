import { CheckCircle, XCircle } from 'lucide-react';
import type { CronJob } from './CronJobsAccordion';

function HealthBadge({ health }: { health?: CronJob['health'] }) {
  if (!health) {
    return (
      <span className="rounded-full border border-border-medium px-2 py-0.5 text-xs text-text-secondary">
        No Data
      </span>
    );
  }

  if (health.recentFailures > 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2 py-0.5 text-xs text-white">
        <XCircle className="h-3 w-3" />
        Unhealthy
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-600 px-2 py-0.5 text-xs text-white">
      <CheckCircle className="h-3 w-3" />
      Healthy
    </span>
  );
}

export default function CronJobsList({
  jobs,
  isLoading,
}: {
  jobs: CronJob[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return <div className="p-4 text-center text-text-secondary">Loading cron jobs...</div>;
  }

  if (jobs.length === 0) {
    return <div className="p-4 text-center text-text-secondary">No cron jobs found</div>;
  }

  return (
    <div className="space-y-2">
      {jobs.map((job) => (
        <div key={job.id} className="rounded-lg border border-border-medium">
          <div className="p-3">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="text-sm font-semibold">
                  {job.name || 'Unnamed Job'}
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-text-secondary">
                  <span
                    className={`rounded-full px-2 py-0.5 ${
                      job.enabled
                        ? 'bg-surface-active text-text-primary'
                        : 'border border-border-medium text-text-secondary'
                    }`}
                  >
                    {job.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <span>
                    {job.schedule.kind}: {String(job.schedule.expr || job.schedule.everyMs || 'N/A')}
                  </span>
                </div>
              </div>
              <HealthBadge health={job.health} />
            </div>
          </div>
          <div className="border-t border-border-medium p-3 text-xs">
            <div>
              <strong>Model:</strong> {job.payload.model || 'N/A'}
            </div>
            <div>
              <strong>Type:</strong> {job.payload.kind}
            </div>
            {job.health && (
              <div className="mt-2 border-t border-border-light pt-2 text-text-secondary">
                Last run: {job.health.lastDuration}ms | Recent runs: {job.health.recentRuns} |
                Failures: {job.health.recentFailures}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
