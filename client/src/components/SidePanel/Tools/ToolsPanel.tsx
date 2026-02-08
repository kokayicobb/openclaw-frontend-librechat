import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

export default function ToolsPanel() {
  const [content, setContent] = useState('Loading...');

  useEffect(() => {
    fetch('/suelo-api/api/suelo-status')
      .then((res) => res.json())
      .then((data) => {
        setContent(data.tools?.toolsMd || 'No TOOLS.md found');
      })
      .catch((err) => setContent(`Error: ${err.message}`));
  }, []);

  return (
    <div className="flex h-full w-full flex-col p-4">
      <div className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
