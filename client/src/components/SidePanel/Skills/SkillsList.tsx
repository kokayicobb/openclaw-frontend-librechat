import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Skill {
  name: string;
  description: string;
  skillMd: string;
}

export default function SkillsList({
  skills,
  isLoading,
}: {
  skills: Skill[];
  isLoading: boolean;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) {
    return <div className="p-4 text-center text-text-secondary">Loading skills...</div>;
  }

  if (skills.length === 0) {
    return <div className="p-4 text-center text-text-secondary">No skills found</div>;
  }

  return (
    <div className="space-y-2">
      {skills.map((skill) => (
        <div key={skill.name} className="rounded-lg border border-border-medium">
          <div
            className="cursor-pointer p-3"
            onClick={() => setExpanded(expanded === skill.name ? null : skill.name)}
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="text-sm font-semibold">{skill.name}</div>
                {skill.description && (
                  <p className="mt-1 text-xs text-text-secondary">{skill.description}</p>
                )}
              </div>
              {expanded === skill.name ? (
                <ChevronDown className="h-4 w-4 text-text-secondary" />
              ) : (
                <ChevronRight className="h-4 w-4 text-text-secondary" />
              )}
            </div>
          </div>
          {expanded === skill.name && (
            <div className="border-t border-border-medium p-3">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown>{skill.skillMd}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
