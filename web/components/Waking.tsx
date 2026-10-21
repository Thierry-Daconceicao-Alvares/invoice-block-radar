"use client";

import { useEffect, useState } from "react";

// Shown while the first answer is awaited; after a few seconds it explains why.
export default function Waking({ what }: { what: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className="panel waking" role="status">
      <span className="dot" aria-hidden="true" />
      <p>
        Loading {what}…
        {slow && (
          <span className="note">
            {" "}
            The API sleeps on its free host when nobody uses it; waking it up takes about a minute. This page fills in
            on its own.
          </span>
        )}
      </p>
    </div>
  );
}
