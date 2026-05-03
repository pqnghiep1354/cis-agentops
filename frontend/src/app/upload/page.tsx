"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { Upload, FileSpreadsheet, CheckCircle, XCircle, AlertCircle, ArrowRight, Loader2, Zap } from "lucide-react";
import { api, UploadResult, TourRunPayload } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge } from "@/components/ui";
import clsx from "clsx";

function ColMapTable({ colMap, missing }: { colMap: Record<string, string>; missing: string[] }) {
  const allFields = ["tour_name", "destination", "duration_days", "raw_description", "price_usd", "highlights", "inclusions", "supplier_name"];
  return (
    <div className="mt-4 rounded-lg overflow-hidden border border-white/5">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-white/5">
            <th className="px-3 py-2 text-left text-mist/40 font-mono">Required Field</th>
            <th className="px-3 py-2 text-left text-mist/40 font-mono">Detected Column</th>
            <th className="px-3 py-2 text-left text-mist/40 font-mono">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {allFields.map(f => {
            const mapped = colMap[f];
            const req = ["tour_name","destination","duration_days","raw_description","price_usd"].includes(f);
            const isMissing = missing.includes(f);
            return (
              <tr key={f} className="hover:bg-white/2">
                <td className="px-3 py-2 font-mono text-mist/70">
                  {f} {req && <span className="text-gold">*</span>}
                </td>
                <td className="px-3 py-2 text-mist/50">{mapped ?? "—"}</td>
                <td className="px-3 py-2">
                  {isMissing ? (
                    <Badge label="MISSING" color="red" />
                  ) : mapped ? (
                    <Badge label="OK" color="green" />
                  ) : (
                    <Badge label="optional" />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TourPreviewCard({ tour, index }: { tour: TourRunPayload; index: number }) {
  return (
    <div className="p-4 rounded-lg bg-white/3 border border-white/5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm text-mist font-medium">{tour.tour_name}</p>
          <p className="text-xs text-mist/40 mt-0.5">{tour.destination} · {tour.duration_days} days · ${tour.price_usd.toLocaleString()}</p>
        </div>
        <Badge label={`#${index + 1}`} />
      </div>
      <p className="text-xs text-mist/50 mt-2 line-clamp-2">{tour.raw_description}</p>
      {tour.highlights.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {tour.highlights.slice(0, 3).map((h, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-gold/10 text-gold/70 border border-gold/15">{h.slice(0, 40)}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<"drop" | "validating" | "ready" | "running">("drop");
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setPhase("validating");
    setError(null);

    try {
      const result = await api.uploadExcel(file);
      setUpload(result);
      // Auto-select all valid tours
      setSelected(new Set(result.tours_preview.map(t => t.tour_name)));
      setPhase("ready");
    } catch (e: any) {
      setError(e.message);
      setPhase("drop");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    maxFiles: 1,
  });

  async function runAll() {
    if (!upload) return;
    setPhase("running");
    try {
      const result = await api.runBatch(upload.upload_id);
      // Navigate to first run's pipeline view
      if (result.run_ids.length > 0) {
        router.push(`/pipeline/${result.run_ids[0]}`);
      } else {
        router.push("/pipeline");
      }
    } catch (e: any) {
      setError(e.message);
      setPhase("ready");
    }
  }

  async function runSingle(tour: TourRunPayload) {
    setPhase("running");
    try {
      const result = await api.runSingle(tour);
      router.push(`/pipeline/${result.run_id}`);
    } catch (e: any) {
      setError(e.message);
      setPhase("ready");
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Upload & Run"
        sub="Upload a supplier Excel file — the system validates schema, then runs the full AI pipeline"
      />

      <div className="max-w-3xl space-y-6">

        {/* Drop zone */}
        {phase === "drop" || phase === "validating" ? (
          <div
            {...getRootProps()}
            className={clsx(
              "relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200",
              isDragActive
                ? "border-gold bg-gold/5"
                : "border-white/10 hover:border-gold/40 hover:bg-white/2",
            )}
          >
            <input {...getInputProps()} />
            {phase === "validating" ? (
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="w-10 h-10 text-gold animate-spin" />
                <p className="text-mist/60">Validating schema…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className={clsx("p-4 rounded-2xl transition-colors", isDragActive ? "bg-gold/20" : "bg-white/5")}>
                  <Upload className={clsx("w-8 h-8", isDragActive ? "text-gold" : "text-mist/40")} />
                </div>
                <div>
                  <p className="text-mist/80 font-medium">Drop your Excel file here</p>
                  <p className="text-mist/40 text-sm mt-1">or click to browse · .xlsx supported</p>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-left w-full max-w-md">
                  {[
                    ["tour_name / name", "Required"],
                    ["destination / country", "Required"],
                    ["summary / description", "Required"],
                    ["duration / duration_days", "Required"],
                    ["price_usd / price", "Required"],
                    ["highlights, inclusions", "Optional"],
                  ].map(([col, req]) => (
                    <div key={col} className="px-2 py-1.5 rounded-lg bg-white/5 border border-white/5">
                      <p className="text-[10px] font-mono text-mist/60">{col}</p>
                      <p className="text-[9px] text-mist/30 mt-0.5">{req}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}

        {error && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
            <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Validation result */}
        {upload && (phase === "ready" || phase === "running") && (
          <>
            <Card gold={upload.valid}>
              <div className="flex items-center gap-3 mb-3">
                {upload.valid
                  ? <CheckCircle className="w-5 h-5 text-green-400" />
                  : <AlertCircle className="w-5 h-5 text-yellow-400" />
                }
                <div>
                  <p className="text-sm text-mist font-medium">{upload.filename}</p>
                  <p className="text-xs text-mist/50">{upload.summary}</p>
                </div>
                <div className="ml-auto flex gap-2">
                  <Badge label={`${upload.tour_count} tours`} color="gold" />
                  {upload.row_errors.length > 0 && (
                    <Badge label={`${upload.row_errors.length} errors`} color="red" />
                  )}
                </div>
              </div>

              <ColMapTable colMap={upload.col_map} missing={upload.missing_required} />

              {upload.row_errors.length > 0 && (
                <div className="mt-3 space-y-1">
                  {upload.row_errors.slice(0, 5).map((e, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-red-400">
                      <XCircle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                      {e}
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Tour previews */}
            {upload.tours_preview.length > 0 && (
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs text-mist/40 font-mono uppercase tracking-widest">
                    Preview ({upload.tours_preview.length} of {upload.tour_count})
                  </p>
                </div>
                <div className="space-y-3">
                  {upload.tours_preview.map((t, i) => (
                    <div key={i} className="relative">
                      <TourPreviewCard tour={t} index={i} />
                      <button
                        onClick={() => runSingle(t)}
                        disabled={phase === "running"}
                        className="absolute top-3 right-3 px-3 py-1 bg-gold/90 hover:bg-gold text-ink text-xs font-medium rounded-lg transition-colors disabled:opacity-40"
                      >
                        Run this tour
                      </button>
                    </div>
                  ))}
                  {upload.tour_count > 3 && (
                    <p className="text-xs text-mist/30 text-center">+ {upload.tour_count - 3} more tours in file</p>
                  )}
                </div>
              </Card>
            )}

            {/* Run all button */}
            {upload.valid && upload.tour_count > 0 && (
              <button
                onClick={runAll}
                disabled={phase === "running"}
                className="w-full flex items-center justify-center gap-3 py-4 bg-gold hover:bg-gold-light text-ink rounded-xl font-medium transition-all disabled:opacity-50"
              >
                {phase === "running" ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> Starting pipeline…</>
                ) : (
                  <><Zap className="w-5 h-5" /> Run all {upload.tour_count} tours through pipeline <ArrowRight className="w-4 h-4" /></>
                )}
              </button>
            )}

            <button
              onClick={() => { setPhase("drop"); setUpload(null); setError(null); }}
              className="w-full py-2 text-sm text-mist/40 hover:text-mist/70 transition-colors"
            >
              Upload a different file
            </button>
          </>
        )}
      </div>
    </PageShell>
  );
}
