import { useCallback, useRef, useState } from "react";

export function Dropzone({
  onFile,
  accept = ".csv,.xlsx,.xls",
  disabled,
}: {
  onFile: (file: File) => void;
  accept?: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  return (
    <div
      className={`dropzone${dragOver ? " dragover" : ""}`}
      data-testid="dropzone"
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragOver(false);
        if (!disabled) handleFiles(event.dataTransfer.files);
      }}
      role="button"
      aria-label="Upload a CSV or Excel file"
    >
      <div className="icon" aria-hidden="true">
        📄
      </div>
      <h3>Drag & drop your CSV or Excel file</h3>
      <p>
        or <strong>click to browse</strong> — supported: .csv, .xlsx, .xls
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        data-testid="file-input"
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
