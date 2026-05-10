import { motion } from "framer-motion";

export function Progress({ value, tone = "cyan" }: { value: number; tone?: "cyan" | "red" | "violet" }) {
  const color = tone === "red" ? "from-rose-500 to-orange-300" : tone === "violet" ? "from-violet-500 to-cyan-300" : "from-cyan-300 to-blue-400";
  return (
    <div className="h-2 overflow-hidden rounded-full bg-white/10">
      <motion.div
        className={`h-full rounded-full bg-gradient-to-r ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      />
    </div>
  );
}
