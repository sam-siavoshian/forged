import type { RefObject } from 'react';
import { useLayoutEffect, useState } from 'react';
import { useScreenSize } from '@/hooks/use-screen-size';
import { PixelTrail } from '@/components/ui/pixel-trail';
import { GooeyFilter } from '@/components/ui/gooey-filter';
import { cn } from '@/lib/utils';

const FILTER_ID = 'gooey-home-hero';

const EXCLUSION_PAD = 14;

/**
 * Radial mask: transparent in the content ellipse, visible in the outer "ring".
 */
function computeAroundMask(
  rootEl: HTMLElement,
  contentEl: HTMLElement,
): string {
  const t = rootEl.getBoundingClientRect();
  const c = contentEl.getBoundingClientRect();
  const rx = (c.width + 2 * EXCLUSION_PAD) / 2;
  const ry = (c.height + 2 * EXCLUSION_PAD) / 2;
  const cx = c.left + c.width / 2 - t.left;
  const cy = c.top + c.height / 2 - t.top;
  /* transparent = hide effect; white = show (mask alpha) */
  return `radial-gradient(ellipse ${rx}px ${ry}px at ${cx}px ${cy}px, transparent 0%, transparent 99.5%, white 99.6%, white 100%)`;
}

/**
 * Mouse-reactive gooey pixel trail for the chat home hero.
 * Trail + wash only show *around* the hero content (not under it) when
 * contentExclusionRef is set. interactionRootRef keeps hovers on the input/chips.
 */
export function PixelBackground({
  className,
  interactionRootRef,
  contentExclusionRef,
}: {
  className?: string;
  interactionRootRef?: RefObject<HTMLElement | null>;
  contentExclusionRef?: RefObject<HTMLElement | null>;
}) {
  const screenSize = useScreenSize();
  const pixelSize = screenSize.lessThan('md') ? 18 : 22;

  const [aroundMask, setAroundMask] = useState<{
    maskImage: string;
    WebkitMaskImage: string;
  } | null>(null);

  useLayoutEffect(() => {
    const root = interactionRootRef?.current;
    const content = contentExclusionRef?.current;
    if (!root || !content) {
      setAroundMask(null);
      return;
    }

    const update = () => {
      const m = computeAroundMask(root, content);
      setAroundMask({ maskImage: m, WebkitMaskImage: m });
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(root);
    ro.observe(content);
    window.addEventListener('resize', update);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [interactionRootRef, contentExclusionRef]);

  const ringMaskStyle =
    aroundMask != null
      ? {
          maskImage: aroundMask.maskImage,
          WebkitMaskImage: aroundMask.WebkitMaskImage,
          maskSize: '100% 100%',
          WebkitMaskSize: '100% 100%',
          maskRepeat: 'no-repeat' as const,
          WebkitMaskRepeat: 'no-repeat' as const,
          maskPosition: '0 0',
          WebkitMaskPosition: '0 0',
        }
      : undefined;

  return (
    <div
      className={cn(
        'absolute inset-0 z-0 overflow-hidden select-none pointer-events-none',
        className,
      )}
      aria-hidden
    >
      <GooeyFilter id={FILTER_ID} strength={2} />
      <div
        className="absolute inset-0 opacity-[0.2] pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 75% 55% at 50% 38%, rgba(56,189,248,0.04) 0%, transparent 58%)',
          ...ringMaskStyle,
        }}
      />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ filter: `url(#${FILTER_ID})`, ...ringMaskStyle }}
      >
        <PixelTrail
          interactionRootRef={interactionRootRef}
          contentExclusionRef={contentExclusionRef}
          pixelSize={pixelSize}
          fadeDuration={950}
          delay={180}
          pixelClassName="bg-[color:var(--color-lime)] opacity-[0.032]"
        />
      </div>
    </div>
  );
}
