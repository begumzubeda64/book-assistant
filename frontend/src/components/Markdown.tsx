import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

// Renders model-generated markdown as sanitized HTML. Model output is untrusted,
// so we always run it through DOMPurify before inserting — never raw HTML.
marked.setOptions({ breaks: true, gfm: true });

export function Markdown({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  const html = useMemo(() => {
    const parsed = marked.parse(content ?? "", { async: false }) as string;
    return DOMPurify.sanitize(parsed);
  }, [content]);

  return (
    <div
      className={className}
      // Sanitized above; safe to inject.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
