import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renderiza Markdown de verdade (briefing, justificativa de recomendacao,
 * resposta do chatbot) em vez de texto cru. Sem isso, links de evidencia e
 * citacoes NVIDIA (`[texto](url)`) nunca ficavam clicaveis na tela - so no
 * PDF exportado, que ja convertia Markdown -> HTML do lado do backend.
 */
export function MarkdownContent({ content, className }: { content: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a className="text-[var(--accent)] underline" href={href} rel="noreferrer" target="_blank">
              {children}
            </a>
          ),
          h1: ({ children }) => <h1 className="text-2xl font-semibold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-6 text-lg font-semibold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-4 font-semibold">{children}</h3>,
          p: ({ children }) => <p className="mt-2 leading-7">{children}</p>,
          ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-5">{children}</ul>,
          li: ({ children }) => <li className="leading-6">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        }}
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
