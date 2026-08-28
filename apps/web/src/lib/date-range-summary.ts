type ParsedToken = {
  month: number;
  year: number;
  monthPrecision: boolean;
};

type ParsedRange = {
  startMonth: number;
  endMonth: number;
  startYear: number;
  endYear: number;
  openEnded: boolean;
};

const MONTHS: Record<string, number> = {
  jan: 0,
  feb: 1,
  mar: 2,
  apr: 3,
  may: 4,
  jun: 5,
  jul: 6,
  aug: 7,
  sep: 8,
  oct: 9,
  nov: 10,
  dec: 11,
};

const DATE_TOKEN = /\b(?:(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+)?((?:19|20)\d{2})\b|\b(present|current|now)\b/gi;

function parseToken(monthName: string | undefined, yearText: string): ParsedToken {
  return {
    month: monthName ? MONTHS[monthName.slice(0, 3).toLocaleLowerCase()] : 0,
    year: Number(yearText),
    monthPrecision: Boolean(monthName),
  };
}

function parseRange(value: string, now: Date): ParsedRange | null {
  const matches = Array.from(value.matchAll(DATE_TOKEN));
  if (matches.length < 2 || matches[0][3]) return null;

  const start = parseToken(matches[0][1], matches[0][2]);
  const openEnded = Boolean(matches[1][3]);
  const end = openEnded ? null : parseToken(matches[1][1], matches[1][2]);
  const startMonth = start.year * 12 + start.month;
  let endMonth: number;

  if (openEnded) {
    endMonth = now.getUTCFullYear() * 12 + now.getUTCMonth() + 1;
  } else if (end?.monthPrecision) {
    endMonth = end.year * 12 + end.month + 1;
  } else if (end) {
    endMonth = end.year === start.year ? (end.year + 1) * 12 : end.year * 12;
  } else {
    return null;
  }

  if (endMonth <= startMonth) return null;
  return {
    startMonth,
    endMonth,
    startYear: start.year,
    endYear: openEnded ? now.getUTCFullYear() : end!.year,
    openEnded,
  };
}

function polishCountWord(value: number, one: string, few: string, many: string) {
  if (value === 1) return one;
  const lastTwo = value % 100;
  const last = value % 10;
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
}

function durationLabel(totalMonths: number, language: "en" | "pl") {
  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;
  const parts: string[] = [];
  if (years) {
    parts.push(language === "pl"
      ? `${years} ${polishCountWord(years, "rok", "lata", "lat")}`
      : `${years} ${years === 1 ? "yr" : "yrs"}`);
  }
  if (months) {
    parts.push(language === "pl"
      ? `${months} ${polishCountWord(months, "miesiąc", "miesiące", "miesięcy")}`
      : `${months} ${months === 1 ? "mo" : "mos"}`);
  }
  return parts.join(" ");
}

export function summarizeDateRanges(
  values: Array<string | null | undefined>,
  now = new Date(),
  language: "en" | "pl" = "en",
) {
  const ranges = values
    .flatMap((value) => value ? [parseRange(value, now)] : [])
    .filter((range): range is ParsedRange => Boolean(range))
    .sort((left, right) => left.startMonth - right.startMonth);
  if (!ranges.length) return null;

  const merged = ranges.reduce<Array<{ startMonth: number; endMonth: number }>>((result, range) => {
    const previous = result.at(-1);
    if (previous && range.startMonth <= previous.endMonth) {
      previous.endMonth = Math.max(previous.endMonth, range.endMonth);
    } else {
      result.push({ startMonth: range.startMonth, endMonth: range.endMonth });
    }
    return result;
  }, []);
  const totalMonths = merged.reduce((sum, range) => sum + range.endMonth - range.startMonth, 0);
  const duration = durationLabel(totalMonths, language);
  if (!duration) return null;

  const startYear = Math.min(...ranges.map((range) => range.startYear));
  const endYear = Math.max(...ranges.map((range) => range.endYear));
  const endLabel = ranges.some((range) => range.openEnded)
    ? language === "pl" ? "obecnie" : "present"
    : String(endYear);
  return `${startYear}–${endLabel} · ${duration}`;
}
