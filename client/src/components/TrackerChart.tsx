import { Line, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import type { TrackerPoint } from "../types";

type Props = {
  points: TrackerPoint[];
};

export default function TrackerChart({ points }: Props) {
  const data = points.map((p) => ({
    t: p.timestamp_ms,
    rtt: p.rtt_ms,
    avg: p.avg_ms,
    threshold: p.threshold_ms,
  }));

  const threshold = data.length ? data[data.length - 1].threshold : undefined;

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            tickFormatter={(v) => new Date(v).toLocaleTimeString()}
            minTickGap={40}
          />
          <YAxis />
          <Tooltip
            labelFormatter={(v) => new Date(Number(v)).toLocaleTimeString()}
          />
          {threshold !== undefined && (
            <ReferenceLine y={threshold} strokeDasharray="4 4" />
          )}
          <Line type="monotone" dataKey="rtt" dot={false} />
          <Line type="monotone" dataKey="avg" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
