export type ViewTransform = { x: number; y: number; scale: number };

export const MIN_PREVIEW_SCALE = 0.12;
export const MAX_PREVIEW_SCALE = 4;

export function pdfPageWidthUrl(url: string) {
  return `${url}#view=FitH`;
}

export function consumePreviewWheel(event: {
  cancelable: boolean;
  preventDefault: () => void;
  stopPropagation: () => void;
}) {
  if (event.cancelable) event.preventDefault();
  event.stopPropagation();
}

export function fitWidthTransform({
  viewportWidth,
  contentWidth,
  minScale = MIN_PREVIEW_SCALE,
  maxScale = MAX_PREVIEW_SCALE,
}: {
  viewportWidth: number;
  contentWidth: number;
  contentHeight?: number;
  minScale?: number;
  maxScale?: number;
}): ViewTransform {
  const scale = contentWidth > 0
    ? Math.min(maxScale, Math.max(minScale, viewportWidth / contentWidth))
    : 1;
  return { x: 0, y: 0, scale };
}

export function wheelTransform(
  current: ViewTransform,
  event: { deltaX: number; deltaY: number; zoom: boolean; pointerX: number; pointerY: number },
): ViewTransform {
  if (!event.zoom) return { ...current, x: current.x - event.deltaX, y: current.y - event.deltaY };
  const scale = Math.min(MAX_PREVIEW_SCALE, Math.max(MIN_PREVIEW_SCALE, current.scale * Math.exp(-event.deltaY * 0.008)));
  const ratio = scale / current.scale;
  return {
    scale,
    x: event.pointerX - (event.pointerX - current.x) * ratio,
    y: event.pointerY - (event.pointerY - current.y) * ratio,
  };
}
