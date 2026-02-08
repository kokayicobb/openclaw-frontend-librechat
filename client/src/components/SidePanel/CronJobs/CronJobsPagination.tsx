import { Button } from '@librechat/client';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function CronJobsPagination({
  onPrevious,
  onNext,
  hasNextPage,
  hasPreviousPage,
  isLoading,
}: {
  onPrevious: () => void;
  onNext: () => void;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  isLoading: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <Button
        size="sm"
        variant="outline"
        onClick={onPrevious}
        disabled={!hasPreviousPage || isLoading}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" />
        Previous
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={onNext}
        disabled={!hasNextPage || isLoading}
        className="flex items-center gap-1"
      >
        Next
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}
