export type Size = { width: number; height: number };
export type Box = { left: number; top: number; width: number; height: number };

// Where an object-contain video lands inside its container, in container pixels.
export function letterbox(container: Size, video: Size): Box {
  if (video.width <= 0 || video.height <= 0) {
    return { left: 0, top: 0, width: container.width, height: container.height };
  }
  const scale = Math.min(container.width / video.width, container.height / video.height);
  const width = video.width * scale;
  const height = video.height * scale;
  return {
    left: (container.width - width) / 2,
    top: (container.height - height) / 2,
    width,
    height,
  };
}

export type Crop = Box & { cursor: { x: number; y: number } };

const clamp = (value: number, low: number, high: number) =>
  Math.min(Math.max(value, low), Math.max(low, high));

// A view-shaped region of the frame, 1/zoom of its width, centred on the point
// unless that would leave the frame. cursor is where the point lands inside
// the crop, as fractions of it.
export function cropAround(
  point: { x: number; y: number },
  video: Size,
  view: Size,
  zoom: number,
): Crop {
  let width = video.width / zoom;
  let height = (width * view.height) / view.width;
  if (height > video.height) {
    height = video.height;
    width = (height * view.width) / view.height;
  }
  const x = point.x * video.width;
  const y = point.y * video.height;
  const left = clamp(x - width / 2, 0, video.width - width);
  const top = clamp(y - height / 2, 0, video.height - height);
  return {
    left,
    top,
    width,
    height,
    cursor: { x: (x - left) / width, y: (y - top) / height },
  };
}
