export function computeRSI(closes: number[], period = 14): number[] {
  const rsiValues: number[] = new Array(period).fill(0);
  if (closes.length < period + 1) return rsiValues;

  let avgGain = 0;
  let avgLoss = 0;

  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) avgGain += diff;
    else avgLoss -= diff;
  }
  avgGain /= period;
  avgLoss /= period;

  const first = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  rsiValues.push(first);

  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    rsiValues.push(parseFloat(rsi.toFixed(2)));
  }

  return rsiValues;
}

export function formatIndianNumber(n: number): string {
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(2) + " L";
  return n.toLocaleString("en-IN");
}

export function formatPrice(p: number): string {
  return p.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
