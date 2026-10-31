type P = { className?: string };

const base = "shrink-0";
const svg = (path: React.ReactNode) =>
  function Icon({ className = "h-5 w-5" }: P) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true" className={`${base} ${className}`}>
        {path}
      </svg>
    );
  };

export const MicIcon = svg(<><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>);
export const SendIcon = svg(<path d="M5 12h13M12 5l7 7-7 7" />);
export const StopIcon = svg(<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />);
export const XIcon = svg(<path d="M6 6l12 12M18 6L6 18" />);
export const CheckIcon = svg(<path d="M5 12.5l4.5 4.5L19 7.5" />);
export const DocIcon = svg(<><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></>);
export const AlertIcon = svg(<><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17.5v.5" /></>);
export const PlusIcon = svg(<path d="M12 5v14M5 12h14" />);
export const SpeakerIcon = svg(<><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></>);
export const SpeakerOffIcon = svg(<><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M17 9.5l5 5M22 9.5l-5 5" /></>);
export const ShieldIcon = svg(<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" />);
export const SpinnerIcon = ({ className = "h-5 w-5" }: P) => (
  <svg viewBox="0 0 24 24" className={`animate-spin ${className}`} aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" fill="none" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
  </svg>
);
