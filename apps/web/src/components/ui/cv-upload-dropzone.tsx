"use client";

import type { ReactNode } from "react";
import { LoaderCircle, UploadCloud } from "lucide-react";

type CvUploadDropzoneProps = {
  label: string;
  hint: string;
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  busy?: boolean;
  keyboardActivation?: boolean;
  children?: ReactNode;
};

export function CvUploadDropzone({
  label, hint, onFilesSelected, disabled = false, busy = false,
  keyboardActivation = false, children,
}: CvUploadDropzoneProps) {
  return (
    <label
      role={keyboardActivation ? "button" : undefined}
      tabIndex={keyboardActivation ? (disabled ? -1 : 0) : undefined}
      aria-label={label}
      aria-disabled={disabled}
      className="flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 bg-muted/15 p-5 text-center outline-none transition-colors hover:bg-muted/30 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring aria-disabled:cursor-not-allowed"
      onKeyDown={keyboardActivation ? (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        if (!disabled) event.currentTarget.querySelector<HTMLInputElement>("input")?.click();
      } : undefined}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        if (!disabled) onFilesSelected(Array.from(event.dataTransfer.files));
      }}
    >
      <input type="file" className="hidden" multiple accept=".pdf,.docx" disabled={disabled}
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? []);
          if (files.length) onFilesSelected(files);
          event.currentTarget.value = "";
        }}
      />
      {busy ? <LoaderCircle className="mb-2 size-5 animate-spin text-muted-foreground" aria-hidden /> : <UploadCloud className="mb-2 size-5 text-muted-foreground" aria-hidden />}
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      {children}
    </label>
  );
}
