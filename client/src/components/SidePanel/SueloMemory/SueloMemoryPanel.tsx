import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@librechat/client';
import ReactMarkdown from 'react-markdown';

export default function SueloMemoryPanel() {
  const [memory, setMemory] = useState({ memoryMd: 'Loading...', koMd: 'Loading...' });

  useEffect(() => {
    fetch('/suelo-api/api/suelo-status')
      .then((res) => res.json())
      .then((data) => {
        setMemory({
          memoryMd: data.memory?.memoryMd || 'No MEMORY.md found',
          koMd: data.memory?.koMd || 'No ko.md found',
        });
      })
      .catch((err) =>
        setMemory({
          memoryMd: `Error: ${err.message}`,
          koMd: `Error: ${err.message}`,
        }),
      );
  }, []);

  return (
    <div className="flex h-full w-full flex-col p-4">
      <Tabs defaultValue="memory" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="memory">MEMORY.md</TabsTrigger>
          <TabsTrigger value="ko">ko.md</TabsTrigger>
        </TabsList>

        <TabsContent value="memory" className="mt-4">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{memory.memoryMd}</ReactMarkdown>
          </div>
        </TabsContent>

        <TabsContent value="ko" className="mt-4">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{memory.koMd}</ReactMarkdown>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
