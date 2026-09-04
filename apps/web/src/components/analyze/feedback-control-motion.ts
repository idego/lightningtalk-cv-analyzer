type Point = readonly [number, number];
type PathPoints = readonly Point[];

const FEEDBACK_BUBBLE_PATHS: readonly PathPoints[] = [
  [
    [13, 2], [17, 2.8], [20, 5.5], [22, 9],
    [21.5, 13], [19, 16.5], [15, 18], [11, 18],
  ],
  [
    [11, 18], [8, 20], [8.5, 17.2], [5.5, 15],
    [4, 11], [4.8, 7], [7, 4], [13, 2],
  ],
];

const FEEDBACK_CLOSE_PATHS: readonly PathPoints[] = [
  [
    [6, 6], [7.7, 7.7], [9.4, 9.4], [11.1, 11.1],
    [12.9, 12.9], [14.6, 14.6], [16.3, 16.3], [18, 18],
  ],
  [
    [18, 6], [16.3, 7.7], [14.6, 9.4], [12.9, 11.1],
    [11.1, 12.9], [9.4, 14.6], [7.7, 16.3], [6, 18],
  ],
];

export function feedbackMorphPath(value: number): string {
  return FEEDBACK_BUBBLE_PATHS.map((line, lineIndex) =>
    line
      .map((point, pointIndex) => {
        const target = FEEDBACK_CLOSE_PATHS[lineIndex][pointIndex];
        const x = point[0] + (target[0] - point[0]) * value;
        const y = point[1] + (target[1] - point[1]) * value;
        return `${pointIndex ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(""),
  ).join("");
}
