import { createElement as h, useRef, useState } from 'react';

interface FormCopy {
  button: string; emailLabel: string; placeholder: string; submit: string; sending: string;
  successTitle: string; successBody: string; validation: string; serverError: string; networkError: string;
  rateLimit: string; retry: string; beta: string;
}
interface PilotProps { className?: string; buttonLabel?: string; placeholder?: string; align?: string; beta?: boolean }

// These hooks and messages are supplied by the mirror's existing React and copy modules.
// The original deployment has no next-intl runtime; preserve its shared-copy boundary.
export function createPilotForm(copy: FormCopy) {
  const buttonClass = 'group relative inline-flex items-stretch gap-1.5 outline-none';
  const labelClass = 'flex items-center justify-center bg-brand-orange text-black font-mono text-xs sm:text-base tracking-wider uppercase px-3 py-2 xs:px-4 xs:py-2.5 sm:px-8 sm:py-4';
  const arrowClass = 'flex items-center justify-center bg-brand-orange text-black w-8 xs:w-9 sm:w-14 aspect-square';
  return function PilotForm(props: PilotProps) {
    const [state, setState] = useState<'button' | 'idle' | 'sending' | 'success' | 'error'>('button');
    const [email, setEmail] = useState('');
    const [error, setError] = useState('');
    const pending = useRef(false);
    const input = useRef<HTMLInputElement>(null);
    const align = props.align === 'center';
    const arrow = h('span', { className: arrowClass, 'aria-hidden': true }, '↗');
    async function submit(event: React.FormEvent<HTMLFormElement>) {
      event.preventDefault();
      if (pending.current) return;
      const value = email.trim();
      if (value.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) { setError(copy.validation); setState('error'); input.current?.focus(); return; }
      pending.current = true; setState('sending'); setError('');
      try {
        const response = await fetch('/api/pilot-requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: value }) });
        if (!response.ok) { setError(response.status === 429 ? copy.rateLimit : response.status === 400 ? copy.validation : copy.serverError); setState('error'); return; }
        const result: unknown = await response.json().catch(() => null);
        if (!result || typeof result !== 'object' || !('accepted' in result) || result.accepted !== true) { setError(copy.serverError); setState('error'); return; }
        setState('success');
      } catch { setError(copy.networkError); setState('error'); }
      finally { pending.current = false; }
    }
    if (props.beta) return h('div', { className: align ? 'flex justify-center' : 'flex' }, h('a', { href: '/app', className: buttonClass }, h('span', { className: labelClass }, copy.beta), arrow));
    if (state === 'button') return h('div', { className: props.className ?? (align ? 'flex justify-center' : 'flex') }, h('button', { type: 'button', className: buttonClass, onClick: () => { setState('idle'); requestAnimationFrame(() => input.current?.focus()); } }, h('span', { className: labelClass }, props.buttonLabel ?? copy.button), arrow));
    if (state === 'success') return h('div', { role: 'status', className: `flex items-center gap-3 py-4 px-5 border border-brand-orange/40 bg-brand-orange/5 rounded-sm max-w-md ${align ? 'mx-auto' : ''}` }, h('span', { className: 'text-brand-orange', 'aria-hidden': true }, '✓'), h('div', null, h('p', { className: 'font-nineties text-lg text-white leading-tight' }, copy.successTitle), h('p', { className: 'font-satoshi text-sm text-white/60' }, copy.successBody)));
    return h('form', { onSubmit: submit, noValidate: true, 'aria-busy': state === 'sending', className: `w-full max-w-md ${align ? 'mx-auto' : ''}` },
      h('div', { className: 'flex items-stretch gap-1.5' },
        h('input', { ref: input, type: 'email', name: 'email', required: true, maxLength: 254, autoComplete: 'email', 'aria-label': copy.emailLabel, 'aria-invalid': state === 'error', 'aria-describedby': state === 'error' ? 'pilot-error' : undefined, value: email, disabled: state === 'sending', onChange: (event: React.ChangeEvent<HTMLInputElement>) => setEmail(event.target.value), placeholder: props.placeholder ?? copy.placeholder, className: 'flex-1 min-w-0 px-3 py-2 xs:px-4 xs:py-2.5 sm:py-4 font-mono text-sm tracking-wide bg-white/[0.03] border border-white/15 rounded-sm text-white placeholder:text-white/30 disabled:opacity-50' }),
        h('button', { type: 'submit', disabled: state === 'sending', className: 'bg-brand-orange text-black px-4 font-mono text-xs', 'aria-label': state === 'sending' ? copy.sending : copy.submit }, state === 'sending' ? copy.sending : '↗')),
      state === 'error' ? h('p', { id: 'pilot-error', role: 'alert', className: 'font-satoshi text-sm text-red-400 mt-3' }, error) : null,
      state === 'error' ? h('button', { type: 'button', className: 'font-mono text-xs uppercase text-brand-orange mt-3', onClick: () => { setState('idle'); setError(''); input.current?.focus(); } }, copy.retry) : null);
  };
}
