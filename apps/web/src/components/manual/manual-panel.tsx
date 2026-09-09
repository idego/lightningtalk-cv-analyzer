"use client";

import { manualContent, manualLabels } from "@/components/manual/manual-content";
import { useCopy } from "@/lib/app-settings";

export function ManualPanel() {
  const { settings } = useCopy();
  const content = manualContent[settings.uiLanguage];
  const labels = manualLabels[settings.uiLanguage];

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8">
      <section className="rounded-xl border bg-card p-5">
        <p className="text-sm leading-relaxed">{content.intro}</p>
        <p className="mt-2 text-xs text-muted-foreground">{content.readTime}</p>
        <nav aria-label={labels.contents} className="mt-4 flex flex-wrap gap-2 text-xs">
          <a href="#quick-start" className="rounded-full border px-3 py-1 hover:bg-muted/40">{labels.quickStart}</a>
          {content.sections.map((section) => (
            <a key={section.id} href={`#${section.id}`} className="rounded-full border px-3 py-1 hover:bg-muted/40">{section.title}</a>
          ))}
          <a href="#boundaries" className="rounded-full border px-3 py-1 hover:bg-muted/40">{content.boundariesTitle}</a>
          <a href="#glossary" className="rounded-full border px-3 py-1 hover:bg-muted/40">{content.glossaryTitle}</a>
        </nav>
      </section>

      <section id="quick-start" className="scroll-mt-20 rounded-xl border bg-card p-5">
        <h3 className="font-medium">{labels.quickStart}</h3>
        <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed">
          {content.quickStart.map((step) => <li key={step}>{step}</li>)}
        </ol>
      </section>

      {content.sections.map((section) => (
        <section key={section.id} id={section.id} className="scroll-mt-20 rounded-xl border bg-card p-5">
          <h3 className="font-medium">{section.title}</h3>
          <p className="mt-1 text-xs text-muted-foreground"><span className="font-medium">{labels.where}:</span> {section.where}</p>
          <p className="mt-2 text-sm leading-relaxed">{section.purpose}</p>
          <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{labels.steps}</h4>
          <ol className="mt-1.5 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed">
            {section.steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{labels.facts}</h4>
          <ul className="mt-1.5 list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
            {section.facts.map((fact) => <li key={fact}>{fact}</li>)}
          </ul>
        </section>
      ))}

      <section id="boundaries" className="scroll-mt-20 rounded-xl border border-amber-500/40 bg-amber-500/5 p-5">
        <h3 className="font-medium">{content.boundariesTitle}</h3>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
          {content.boundaries.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <section id="glossary" className="scroll-mt-20 rounded-xl border bg-card p-5">
        <h3 className="font-medium">{content.glossaryTitle}</h3>
        <dl className="mt-3 divide-y text-sm">
          {content.glossary.map((entry) => (
            <div key={entry.term} className="grid gap-1 py-2 sm:grid-cols-[10rem_1fr] sm:gap-4">
              <dt className="font-medium">{entry.term}</dt>
              <dd className="text-muted-foreground">{entry.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
