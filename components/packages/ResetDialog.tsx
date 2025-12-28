'use client';

export function ResetDialog({ onConfirm, onCancel }: { onConfirm: () => Promise<void>; onCancel: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div style={{ textAlign: 'center', fontSize: 28 }}>🚨</div>
        <h3 style={{ textAlign: 'center' }}>Factory Reset</h3>
        <p className="muted" style={{ textAlign: 'center' }}>
          This will delete <strong>ALL</strong> packages. Type CONFIRM to proceed.
        </p>
        <input className="input" id="confirm-input" placeholder="CONFIRM" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
          <button className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn danger"
            onClick={async () => {
              const el = document.getElementById('confirm-input') as HTMLInputElement | null;
              if (el?.value === 'CONFIRM') {
                await onConfirm();
              }
            }}
          >
            💣 Delete All
          </button>
        </div>
      </div>
    </div>
  );
}
