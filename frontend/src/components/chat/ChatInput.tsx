import { useState, useRef, useCallback } from 'react';

interface ChatInputProps {
  onSubmit: (task: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSubmit, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, disabled, onSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, []);

  const canSubmit = value.trim().length > 0 && !disabled;

  return (
    <div className="w-full max-w-[680px]">
      {/* Outer glow ring on focus */}
      <div
        className="rounded-[20px] p-[1px] transition-all duration-300"
        style={{
          background: focused
            ? 'linear-gradient(135deg, rgba(200,255,0,0.15), rgba(200,255,0,0.03), rgba(200,255,0,0.08))'
            : 'rgba(255,255,255,0.04)',
          boxShadow: focused
            ? '0 0 30px rgba(200,255,0,0.06), 0 0 60px rgba(200,255,0,0.02)'
            : 'none',
        }}
      >
        <div
          className="relative flex items-end gap-3 rounded-[19px] px-5 py-4"
          style={{
            background: 'rgba(0,0,0,0.4)',
            boxShadow: `
              inset 0 8px 24px rgba(0,0,0,0.6),
              inset 0 2px 6px rgba(0,0,0,0.4),
              inset 0 -1px 3px rgba(255,255,255,0.02),
              0 1px 0 rgba(255,255,255,0.03)
            `,
          }}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => { setValue(e.target.value); handleInput(); }}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={placeholder || 'Send a message...'}
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none bg-transparent text-[15px] text-text placeholder-text-muted/60
                       focus:outline-none disabled:opacity-30 leading-[1.6] py-0.5 px-0
                       min-h-[28px] max-h-[120px]"
            style={{ fontFamily: 'var(--font-body)' }}
          />
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="shrink-0 flex items-center justify-center w-9 h-9 rounded-xl
                       transition-all duration-200"
            style={{
              background: canSubmit ? 'var(--color-lime)' : 'rgba(255,255,255,0.04)',
              color: canSubmit ? '#09090b' : 'var(--color-text-muted)',
              boxShadow: canSubmit
                ? 'inset 0 -3px 8px rgba(0,0,0,0.15), inset 0 2px 4px rgba(255,255,255,0.25), 0 2px 12px rgba(200,255,0,0.2)'
                : 'inset 0 4px 8px rgba(0,0,0,0.3)',
              opacity: canSubmit ? 1 : 0.4,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
