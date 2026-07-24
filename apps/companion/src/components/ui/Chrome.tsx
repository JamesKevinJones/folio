import "./ui.css";

export function BootSplash({ ready }: { ready: boolean }) {
  return (
    <div className={`boot ${ready ? "boot-out" : ""}`}>
      <div className="boot-mark">F</div>
      <div className="boot-loading">LOADING</div>
      <div className="boot-sub">connecting research desk</div>
    </div>
  );
}

export function IdleHero() {
  return (
    <div className="idle-hero">
      <h1>
        <span>FOLIO</span>
        <span>research desk</span>
      </h1>
      <p>Ask anything. See the sources.</p>
      <p className="hint-line">Type below or hold the mic — sources appear after Folio researches.</p>
    </div>
  );
}

export function BracketStatus({ value }: { value: string }) {
  return <span className="bracket">[{value}]</span>;
}

export function Counter({ label, value }: { label: string; value: number }) {
  return (
    <span className="counter">
      {label} {String(value).padStart(2, "0")}
    </span>
  );
}
