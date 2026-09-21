import type { ReactNode } from "react";

/**
 * Renders the small subset of formatting Sigvi is told to use — paragraphs,
 * "- " bullets, "1." lists and **bold** — as real React elements. Model output
 * is never injected as HTML: anything else (links, tags, headings) shows as
 * plain text, so a reply can't add markup or scripts to the page.
 */

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    const bold = /^\*\*([^*]+)\*\*$/.exec(part);
    return bold ? <strong key={`${keyPrefix}-${index}`}>{bold[1]}</strong> : part;
  });
}

export function FormattedMessage({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    const key = `p-${blocks.length}`;
    blocks.push(
      <p key={key}>
        {paragraph.map((line, index) => (
          <span key={index}>
            {index > 0 && <br />}
            {inline(line, `${key}-${index}`)}
          </span>
        ))}
      </p>,
    );
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    const key = `l-${blocks.length}`;
    const items = list.items.map((item, index) => (
      <li key={index}>{inline(item, `${key}-${index}`)}</li>
    ));
    blocks.push(list.ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
    list = null;
  };

  for (const line of text.split("\n")) {
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const match = bullet ?? numbered;
    if (match) {
      flushParagraph();
      const ordered = numbered !== null;
      if (list && list.ordered !== ordered) flushList();
      list ??= { ordered, items: [] };
      list.items.push(match[1]);
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();

  return <>{blocks}</>;
}
