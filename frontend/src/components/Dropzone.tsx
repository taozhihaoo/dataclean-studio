import { useCallback, useRef, useState } from "react";

export function Dropzone({
  onFiles,
  accept = ".csv,.xlsx,.xls",
  disabled,
  multiple = false,
}: {
  onFiles: (files: File[]) => void;
  accept?: string;
  disabled?: boolean;
  multiple?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      onFiles(Array.from(files));
    },
    [onFiles]
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
      aria-label={multiple ? "Upload one or more CSV or Excel files" : "Upload a CSV or Excel file"}
    >
      <div className="icon" aria-hidden="true">
        📄
      </div>
      <h3>
        {multiple
          ? "Drag & drop CSV or Excel files (up to 10)"
          : "Drag & drop your CSV or Excel file"}
      </h3>
      <p>
        or <strong>click to browse</strong> — supported: .csv, .xlsx, .xls
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
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
