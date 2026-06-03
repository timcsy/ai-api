import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { presetRange, type RangePreset, type TimeRange } from "@/lib/time-range";

/**
 * Shared time-range selector (Phase 14). Used by home + usage pages so every
 * charted page offers the same 本週/本月/本季/自訂 control.
 */
export function TimeRangeSelect({
  value,
  onChange,
}: {
  value: TimeRange;
  onChange: (next: TimeRange) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <Label htmlFor="range-preset">時段</Label>
        <Select
          value={value.preset}
          onValueChange={(p) => onChange(presetRange(p as RangePreset, value))}
        >
          <SelectTrigger id="range-preset" className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="week">本週</SelectItem>
            <SelectItem value="month">本月</SelectItem>
            <SelectItem value="quarter">本季</SelectItem>
            <SelectItem value="custom">自訂</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {value.preset === "custom" && (
        <>
          <div>
            <Label htmlFor="range-from">起始</Label>
            <Input
              id="range-from"
              type="date"
              value={value.from}
              onChange={(e) => onChange({ ...value, from: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="range-to">結束</Label>
            <Input
              id="range-to"
              type="date"
              value={value.to}
              onChange={(e) => onChange({ ...value, to: e.target.value })}
            />
          </div>
        </>
      )}
    </div>
  );
}
