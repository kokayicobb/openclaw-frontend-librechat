import { useState, useEffect } from 'react';
import { Input } from '@librechat/client';
import { Search, Code2 } from 'lucide-react';
import SkillsList from './SkillsList';
import SkillsPagination from './SkillsPagination';

interface Skill {
  name: string;
  description: string;
  skillMd: string;
}

export default function SkillsAccordion() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 10;

  useEffect(() => {
    fetch('/suelo-api/api/suelo-status')
      .then((res) => res.json())
      .then((data) => {
        setSkills(data.skills || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching skills:', err);
        setLoading(false);
      });
  }, []);

  const filteredSkills = skills.filter(
    (skill) =>
      skill.name.toLowerCase().includes(search.toLowerCase()) ||
      skill.description.toLowerCase().includes(search.toLowerCase()),
  );

  const totalPages = Math.ceil(filteredSkills.length / perPage);
  const paginatedSkills = filteredSkills.slice((page - 1) * perPage, page * perPage);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="mt-2 space-y-2">
        {/* Search */}
        <div className="relative px-2">
          <Search className="absolute left-5 top-3 h-4 w-4 text-text-secondary" />
          <Input
            type="text"
            placeholder="Search skills..."
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
          <SkillsList skills={paginatedSkills} isLoading={loading} />
        </div>
      </div>

      {/* Pagination */}
      <div className="px-2 pb-3 pt-2">
        <SkillsPagination
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
