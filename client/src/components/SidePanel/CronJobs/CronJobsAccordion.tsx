import { useState, useEffect } from 'react';
import { Input } from '@librechat/client';
import { Search } from 'lucide-react';
import CronJobsList from './CronJobsList';
import CronJobsPagination from './CronJobsPagination';

export interface CronJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule: { kind: string; [key: string]: unknown };
  payload: { kind: string; model?: string; [key: string]: unknown };
  health?: {
    lastStatus: string;
    lastDuration: number;
    recentRuns: number;
    recentFailures: number;
  };
}

export default function CronJobsAccordion() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 10;

  useEffect(() => {
    fetch('/suelo-api/api/suelo-status')
      .then((res) => res.json())
      .then((data) => {
        const cronJobs = data.crons || [];
        // Take last 100 jobs
        setJobs(cronJobs.slice(-100).reverse());
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching cron jobs:', err);
        setLoading(false);
      });
  }, []);

  const filteredJobs = jobs.filter(
    (job) =>
      job.name?.toLowerCase().includes(search.toLowerCase()) ||
      job.payload?.model?.toLowerCase().includes(search.toLowerCase()),
  );

  const totalPages = Math.ceil(filteredJobs.length / perPage);
  const paginatedJobs = filteredJobs.slice((page - 1) * perPage, page * perPage);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="mt-2 space-y-2">
        {/* Search */}
        <div className="relative px-2">
          <Search className="absolute left-5 top-3 h-4 w-4 text-text-secondary" />
          <Input
            type="text"
            placeholder="Search cron jobs..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-10"
          />
        </div>

        {/* List */}
        <div className="relative flex h-full flex-col px-2">
          <CronJobsList jobs={paginatedJobs} isLoading={loading} />
        </div>
      </div>

      {/* Pagination */}
      <div className="px-2 pb-3 pt-2">
        <CronJobsPagination
          onPrevious={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
          hasNextPage={page < totalPages}
          hasPreviousPage={page > 1}
          isLoading={loading}
        />
      </div>
    </div>
  );
}
