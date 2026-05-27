"use client";

import { useEffect, useRef, useState } from "react";
import { Mic2 } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import {
  GitHubLogo,
  GoogleDocsLogo,
  JiraLogo,
  LinearLogo,
  SlackLogo,
} from "@/components/icons/brand-logos";

/*
 * ANIMATION STORYBOARD
 *
 * Read top-to-bottom. Each `at` value is ms after the demo enters view.
 *
 *     0ms   graph is dim, record waits for source agreement
 *   180ms   source pucks appear as quiet background inputs
 *   500ms   Slack packet feeds the graph, then Decision resolves
 *  1400ms   GitHub packet feeds the graph, then Sources resolves
 *  2300ms   Meeting packet feeds the graph, then Why resolves
 *  3200ms   Docs packet feeds the graph, then Systems resolves
 *  4100ms   Linear/Jira packet feeds the graph, then People resolves
 *  5000ms   record status becomes verified from five sources
 *  5300ms   record fills line by line
 *  6500ms   final calm state holds for reading
 * 12000ms   soft reset if the demo is still visible
 * 12700ms   replay begins from the initial state
 */

const STAGE = {
  sources: 1,
  slackFeed: 2,
  decisionResolved: 3,
  githubFeed: 4,
  sourcesResolved: 5,
  meetingFeed: 6,
  whyResolved: 7,
  docsFeed: 8,
  systemsResolved: 9,
  linearFeed: 10,
  peopleResolved: 11,
  verified: 12,
  recordRows: 13,
  calm: 14,
} as const;

const TIMING = {
  sources: 180, // source pucks appear
  slackFeed: 500, // Slack packet enters graph
  decisionResolved: 1000, // Decision node resolves
  githubFeed: 1400, // GitHub packet enters graph
  sourcesResolved: 1900, // Sources node resolves
  meetingFeed: 2300, // Meeting packet enters graph
  whyResolved: 2800, // Why node resolves
  docsFeed: 3200, // Docs packet enters graph
  systemsResolved: 3700, // Systems node resolves
  linearFeed: 4100, // Linear/Jira packet enters graph
  peopleResolved: 4600, // People node resolves
  verified: 5000, // record status verifies
  recordRows: 5300, // record rows reveal
  calm: 6500, // final calm state
} as const;

const LOOP = {
  finalHold: 5500, // ms verified record stays readable before reset
  resetHold: 700, // ms initial state rests before replay
  rootMargin: "-18% 0px -18% 0px", // start only when the demo is comfortably visible
  threshold: 0.22, // visible ratio required before playback starts
} as const;

const STORYBOARD_STEPS = [
  { at: TIMING.sources, stage: STAGE.sources },
  { at: TIMING.slackFeed, stage: STAGE.slackFeed },
  { at: TIMING.decisionResolved, stage: STAGE.decisionResolved },
  { at: TIMING.githubFeed, stage: STAGE.githubFeed },
  { at: TIMING.sourcesResolved, stage: STAGE.sourcesResolved },
  { at: TIMING.meetingFeed, stage: STAGE.meetingFeed },
  { at: TIMING.whyResolved, stage: STAGE.whyResolved },
  { at: TIMING.docsFeed, stage: STAGE.docsFeed },
  { at: TIMING.systemsResolved, stage: STAGE.systemsResolved },
  { at: TIMING.linearFeed, stage: STAGE.linearFeed },
  { at: TIMING.peopleResolved, stage: STAGE.peopleResolved },
  { at: TIMING.verified, stage: STAGE.verified },
  { at: TIMING.recordRows, stage: STAGE.recordRows },
  { at: TIMING.calm, stage: STAGE.calm },
] as const;

const SOURCE_PUCKS = {
  size: 72, // px desktop puck diameter
  offsetY: 10, // px source pucks enter from
  packetSize: 36, // px moving packet
  packetDuration: 0.72, // seconds for source packet to reach core
  stagger: 0.055, // seconds between source puck entrances
  spring: { type: "spring" as const, stiffness: 340, damping: 32 },
  items: [
    {
      source: "Slack",
      point: { x: 132, y: 168 },
      className: "xl:left-[72px] xl:top-[126px]",
      feedStage: STAGE.slackFeed,
      resolveStage: STAGE.decisionResolved,
      resolves: "Decision",
    },
    {
      source: "GitHub PR",
      point: { x: 132, y: 352 },
      className: "xl:left-[72px] xl:top-[310px]",
      feedStage: STAGE.githubFeed,
      resolveStage: STAGE.sourcesResolved,
      resolves: "Sources",
    },
    {
      source: "Meeting",
      point: { x: 250, y: 226 },
      className: "xl:left-[196px] xl:top-[184px]",
      feedStage: STAGE.meetingFeed,
      resolveStage: STAGE.whyResolved,
      resolves: "Why",
    },
    {
      source: "Docs",
      point: { x: 132, y: 548 },
      className: "xl:left-[72px] xl:top-[506px]",
      feedStage: STAGE.docsFeed,
      resolveStage: STAGE.systemsResolved,
      resolves: "Systems",
    },
    {
      source: "Linear/Jira",
      point: { x: 250, y: 468 },
      className: "xl:left-[196px] xl:top-[426px]",
      feedStage: STAGE.linearFeed,
      resolveStage: STAGE.peopleResolved,
      resolves: "People",
    },
  ],
} as const;

const GRAPH = {
  corePoint: { x: 522, y: 344 },
  recordPoint: { x: 774, y: 344 },
  mobileSize: 330, // px max graph size on mobile
  desktopSize: 520, // px graph size on desktop theater
  coreSize: 148, // px center node size
  statusOffsetY: 18, // px status pill offset below graph
  spring: { type: "spring" as const, stiffness: 260, damping: 28 },
  nodes: [
    { label: "Decision", resolveStage: STAGE.decisionResolved, className: "left-[42%] top-[8%]" },
    { label: "Sources", resolveStage: STAGE.sourcesResolved, className: "left-[24%] bottom-[8%]" },
    { label: "Why", resolveStage: STAGE.whyResolved, className: "right-[2%] top-[36%]" },
    { label: "Systems", resolveStage: STAGE.systemsResolved, className: "right-[14%] bottom-[14%]" },
    { label: "People", resolveStage: STAGE.peopleResolved, className: "left-[0%] top-[43%]" },
  ],
  glow: {
    quiet: "0 0 0 rgba(73,214,181,0)",
    active: "0 0 96px rgba(73,214,181,0.20)",
    calm: "0 0 40px rgba(73,214,181,0.10)",
  },
} as const;

const RECORD = {
  enterOffsetX: 18, // px record enters from
  rowOffsetY: 8, // px record rows enter from
  rowStagger: 0.085, // seconds between record sections
  spring: { type: "spring" as const, stiffness: 240, damping: 30 },
  sections: [
    {
      label: "Decision",
      values: ["Keep tenant isolation at database level"],
    },
    {
      label: "Why",
      values: ["Enterprise customers need strict data boundaries"],
    },
    {
      label: "People involved",
      values: ["Ayan", "Madina", "Bekbol"],
    },
    {
      label: "Sources",
      values: ["Slack thread", "PR #418", "Architecture note"],
    },
    {
      label: "Affected systems",
      values: ["Auth", "Billing", "Enterprise plan"],
    },
  ],
} as const;

type DemoStage = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14;
type SourceItem = (typeof SOURCE_PUCKS.items)[number];
type SourceName = SourceItem["source"];

function useDemoInView() {
  const ref = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setInView(true);
      return;
    }

    const observer = new window.IntersectionObserver(
      ([entry]) => {
        setInView(entry.isIntersecting);
      },
      {
        rootMargin: LOOP.rootMargin,
        threshold: LOOP.threshold,
      }
    );

    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  return { ref, inView };
}

function useDemoStage(reduceMotion: boolean, inView: boolean): DemoStage {
  const [stage, setStage] = useState<DemoStage>(reduceMotion ? STAGE.calm : 0);

  useEffect(() => {
    const timers: number[] = [];

    if (reduceMotion) {
      setStage(STAGE.calm);
      return () => undefined;
    }

    if (!inView) {
      setStage(0);
      return () => undefined;
    }

    const playCycle = () => {
      setStage(0);

      STORYBOARD_STEPS.forEach((step) => {
        timers.push(window.setTimeout(() => setStage(step.stage), step.at));
      });

      timers.push(
        window.setTimeout(() => setStage(0), TIMING.calm + LOOP.finalHold)
      );
    };

    playCycle();
    const replayTimer = window.setInterval(
      playCycle,
      TIMING.calm + LOOP.finalHold + LOOP.resetHold
    );

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      window.clearInterval(replayTimer);
    };
  }, [inView, reduceMotion]);

  return stage;
}

function SourceLogo({
  source,
  className,
}: {
  source: SourceName;
  className?: string;
}) {
  if (source === "Slack") {
    return <SlackLogo width={24} height={24} color="currentColor" className={className} />;
  }

  if (source === "GitHub PR") {
    return <GitHubLogo width={24} height={24} className={className} />;
  }

  if (source === "Meeting") {
    return <Mic2 aria-hidden="true" className={className} size={24} strokeWidth={1.8} />;
  }

  if (source === "Docs") {
    return <GoogleDocsLogo width={24} height={24} className={className} />;
  }

  return (
    <span className="flex items-center justify-center" aria-hidden="true">
      <LinearLogo width={20} height={20} className={className} />
      <JiraLogo width={20} height={20} className="-ml-2 text-current opacity-70" />
    </span>
  );
}

function isSourceActive(stage: DemoStage, item: SourceItem) {
  return stage >= item.feedStage && stage < item.resolveStage;
}

function SourcePuck({
  item,
  index,
  stage,
  reduceMotion,
}: {
  item: SourceItem;
  index: number;
  stage: DemoStage;
  reduceMotion: boolean;
}) {
  const active = isSourceActive(stage, item);
  const absorbed = stage >= item.resolveStage;
  const leadIdle = index === 0 && stage < item.feedStage;

  return (
    <motion.div
      aria-label={`${item.source} feeds ${item.resolves}`}
      className={`relative flex flex-col items-center gap-2 text-center xl:absolute xl:w-[92px] ${item.className}`}
      initial={
        reduceMotion
          ? false
          : {
              opacity: leadIdle ? 0.72 : 0,
              y: leadIdle ? 0 : SOURCE_PUCKS.offsetY,
              scale: leadIdle ? 1 : 0.96,
            }
      }
      animate={{
        opacity: stage >= STAGE.sources ? 1 : leadIdle ? 0.72 : 0,
        y: stage >= STAGE.sources || leadIdle ? 0 : SOURCE_PUCKS.offsetY,
        scale: active ? 1.04 : 1,
      }}
      transition={{
        ...SOURCE_PUCKS.spring,
        delay: reduceMotion ? 0 : index * SOURCE_PUCKS.stagger,
      }}
    >
      <motion.div
        className="flex h-[72px] w-[72px] items-center justify-center rounded-full border border-white/[0.08] bg-[#11151C]/88 text-[#D7DCE2] shadow-[0_18px_48px_rgba(0,0,0,0.24)] backdrop-blur-md"
        animate={{
          borderColor: active
            ? "rgba(73, 214, 181, 0.42)"
            : absorbed
              ? "rgba(73, 214, 181, 0.18)"
              : leadIdle
                ? "rgba(73, 214, 181, 0.22)"
                : "rgba(255, 255, 255, 0.08)",
          boxShadow:
            active && !reduceMotion
              ? "0 0 34px rgba(73,214,181,0.20)"
              : "0 18px 48px rgba(0,0,0,0.24)",
          color: active ? "#FFFFFF" : absorbed || leadIdle ? "#C9D3DB" : "#8E98A6",
        }}
        transition={SOURCE_PUCKS.spring}
      >
        <SourceLogo source={item.source} className="h-6 w-6" />
      </motion.div>
      <p className="font-mono text-[11px] font-semibold leading-4 text-[#E6EAEE]">
        {item.source === "GitHub PR" ? "GitHub" : item.source}
      </p>
    </motion.div>
  );
}

function SourcePuckLayer({
  stage,
  reduceMotion,
}: {
  stage: DemoStage;
  reduceMotion: boolean;
}) {
  return (
    <article
      aria-label="Sources feeding the decision graph"
      className="relative z-10 rounded-xl border border-white/[0.08] bg-[#0B0D12]/78 p-4 xl:contents"
    >
      <div className="grid grid-cols-2 gap-5 sm:grid-cols-5 xl:contents">
        {SOURCE_PUCKS.items.map((item, index) => (
          <SourcePuck
            key={item.source}
            item={item}
            index={index}
            stage={stage}
            reduceMotion={reduceMotion}
          />
        ))}
      </div>
    </article>
  );
}

function FeedingStreams({
  stage,
  reduceMotion,
}: {
  stage: DemoStage;
  reduceMotion: boolean;
}) {
  return (
    <>
      <p className="sr-only">Source packets feed the decision graph</p>
      <svg
        className="pointer-events-none absolute inset-0 z-0 hidden h-full w-full xl:block"
        viewBox="0 0 1000 690"
        fill="none"
        aria-hidden="true"
      >
        {SOURCE_PUCKS.items.map((item, index) => {
          const active = isSourceActive(stage, item);
          const absorbed = stage >= item.resolveStage;
          const leadIdle = index === 0 && stage < item.feedStage;
          const midX = item.point.x < 170 ? 330 : 386;
          const path = `M${item.point.x} ${item.point.y} C${midX} ${item.point.y} 402 ${GRAPH.corePoint.y} ${GRAPH.corePoint.x} ${GRAPH.corePoint.y}`;

          return (
            <g key={item.source}>
              <motion.path
                d={path}
                stroke={leadIdle ? "rgba(73,214,181,0.22)" : "rgba(73,214,181,0.17)"}
                strokeWidth="1"
                strokeLinecap="round"
                initial={
                  reduceMotion
                    ? false
                    : {
                        pathLength: leadIdle ? 1 : 0,
                        opacity: leadIdle ? 0.34 : 0,
                      }
                }
                animate={{
                  pathLength: absorbed || active || leadIdle ? 1 : 0,
                  opacity: absorbed || active ? 0.72 : leadIdle ? 0.34 : 0,
                }}
                transition={{
                  duration: reduceMotion ? 0 : 0.55,
                  ease: "easeInOut",
                }}
              />
              {active && !reduceMotion && (
                <motion.foreignObject
                  width={SOURCE_PUCKS.packetSize}
                  height={SOURCE_PUCKS.packetSize}
                  initial={{
                    x: item.point.x - SOURCE_PUCKS.packetSize / 2,
                    y: item.point.y - SOURCE_PUCKS.packetSize / 2,
                    opacity: 0,
                    scale: 0.72,
                  }}
                  animate={{
                    x: [
                      item.point.x - SOURCE_PUCKS.packetSize / 2,
                      midX - SOURCE_PUCKS.packetSize / 2,
                      GRAPH.corePoint.x - SOURCE_PUCKS.packetSize / 2,
                    ],
                    y: [
                      item.point.y - SOURCE_PUCKS.packetSize / 2,
                      item.point.y - SOURCE_PUCKS.packetSize / 2,
                      GRAPH.corePoint.y - SOURCE_PUCKS.packetSize / 2,
                    ],
                    opacity: [0, 1, 1, 0],
                    scale: [0.72, 1, 0.84, 0.36],
                  }}
                  transition={{
                    duration: SOURCE_PUCKS.packetDuration,
                    ease: "easeInOut",
                  }}
                >
                  <div className="flex h-full w-full items-center justify-center rounded-full border border-[rgba(var(--color-teal-rgb),0.34)] bg-[#0C1717]/95 text-white shadow-[0_0_30px_rgba(73,214,181,0.24)] backdrop-blur-sm">
                    <SourceLogo source={item.source} className="h-5 w-5" />
                  </div>
                </motion.foreignObject>
              )}
            </g>
          );
        })}

        <motion.path
          d={`M${GRAPH.corePoint.x + 118} ${GRAPH.corePoint.y} C662 ${GRAPH.corePoint.y} 706 ${GRAPH.recordPoint.y} ${GRAPH.recordPoint.x} ${GRAPH.recordPoint.y}`}
          stroke="rgba(73,214,181,0.22)"
          strokeWidth="1.15"
          strokeLinecap="round"
          initial={reduceMotion ? false : { pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: stage >= STAGE.verified ? 1 : 0,
            opacity: stage >= STAGE.verified ? 0.86 : 0,
          }}
          transition={{ duration: reduceMotion ? 0 : 0.75, ease: "easeInOut" }}
        />
      </svg>
    </>
  );
}

function KnowledgeGraphCore({
  stage,
  reduceMotion,
  desktopTheater = false,
}: {
  stage: DemoStage;
  reduceMotion: boolean;
  desktopTheater?: boolean;
}) {
  const resolvedCount = GRAPH.nodes.filter((node) => stage >= node.resolveStage).length;
  const verified = stage >= STAGE.verified;
  const activePulse = stage >= STAGE.slackFeed && stage < STAGE.verified;

  return (
    <article
      className={
        desktopTheater
          ? "relative z-10 min-h-[420px] overflow-hidden rounded-xl border border-[rgba(var(--color-teal-rgb),0.20)] bg-[#07100F]/86 p-4 text-left xl:absolute xl:left-[49%] xl:top-1/2 xl:min-h-0 xl:w-[560px] xl:-translate-x-1/2 xl:-translate-y-1/2 xl:overflow-visible xl:border-0 xl:bg-transparent xl:p-0"
          : "relative z-10 min-h-[420px] overflow-hidden rounded-xl border border-[rgba(var(--color-teal-rgb),0.20)] bg-[#07100F]/86 p-4 text-left"
      }
    >
      <div className={desktopTheater ? "mb-2 flex items-center justify-between gap-3 px-2" : "mb-4 flex items-center justify-between gap-3"}>
        <p className="font-mono text-xs font-semibold text-[var(--color-teal)]">
          Decision graph
        </p>
        <motion.span
          className="rounded-full border border-[rgba(var(--color-teal-rgb),0.18)] px-2.5 py-1 font-mono text-[10px] uppercase text-[#9CA3AF]"
          animate={{
            opacity: verified ? 1 : resolvedCount > 0 ? 0.82 : 0.48,
            borderColor: verified
              ? "rgba(73,214,181,0.38)"
              : "rgba(255,255,255,0.08)",
            color: verified ? "var(--color-teal)" : "#9CA3AF",
          }}
        >
          {verified ? "5 sources matched" : "matching sources"}
        </motion.span>
      </div>

      <div
        className="relative mx-auto mt-2 aspect-square"
        style={{
          maxWidth: desktopTheater ? GRAPH.desktopSize : GRAPH.mobileSize,
        }}
      >
        <motion.div
          className="absolute inset-[9%] rounded-full border border-[rgba(var(--color-teal-rgb),0.18)] bg-[rgba(var(--color-teal-rgb),0.03)]"
          animate={
            reduceMotion
              ? undefined
              : {
                  boxShadow: activePulse || verified
                    ? [GRAPH.glow.quiet, GRAPH.glow.active, GRAPH.glow.calm]
                    : GRAPH.glow.quiet,
                  scale: activePulse ? [1, 1.018, 1] : 1,
                }
          }
          transition={{
            duration: stage >= STAGE.calm ? 3.4 : 1.2,
            repeat: stage >= STAGE.calm ? Infinity : 0,
            ease: "easeInOut",
          }}
        />

        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 380 380" fill="none" aria-hidden="true">
          {[92, 128, 158].map((radius, index) => (
            <motion.circle
              key={radius}
              cx="190"
              cy="190"
              r={radius}
              stroke="rgba(73,214,181,0.18)"
              strokeWidth="1"
              initial={reduceMotion ? false : { pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: resolvedCount > index ? 1 : 0,
                opacity: resolvedCount > index ? 1 : 0.12,
              }}
              transition={{
                duration: reduceMotion ? 0 : 0.62,
                ease: "easeInOut",
              }}
            />
          ))}
          {[
            { line: "M190 190 L190 44", resolveStage: STAGE.decisionResolved },
            { line: "M190 190 L82 300", resolveStage: STAGE.sourcesResolved },
            { line: "M190 190 L332 132", resolveStage: STAGE.whyResolved },
            { line: "M190 190 L296 296", resolveStage: STAGE.systemsResolved },
            { line: "M190 190 L42 172", resolveStage: STAGE.peopleResolved },
          ].map((edge) => (
            <motion.path
              key={edge.line}
              d={edge.line}
              stroke="rgba(73,214,181,0.24)"
              strokeWidth="1"
              strokeLinecap="round"
              initial={reduceMotion ? false : { pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: stage >= edge.resolveStage ? 1 : 0,
                opacity: stage >= edge.resolveStage ? 1 : 0,
              }}
              transition={{
                duration: reduceMotion ? 0 : 0.55,
                ease: "easeInOut",
              }}
            />
          ))}
        </svg>

        <motion.div
          className="absolute left-1/2 top-1/2 flex h-[148px] w-[148px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-[rgba(var(--color-teal-rgb),0.42)] bg-[#0D1717] text-center shadow-[0_22px_86px_rgba(0,0,0,0.38)]"
          animate={{
            scale: activePulse ? 1.035 : stage >= STAGE.sources ? 1 : 0.94,
            opacity: stage >= STAGE.sources ? 1 : 0.68,
          }}
          transition={GRAPH.spring}
        >
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#7A8494]">
              ContextOS
            </p>
            <p className="mt-1 text-sm font-semibold text-white">
              Decision graph
            </p>
          </div>
        </motion.div>

        {GRAPH.nodes.map((node) => {
          const resolved = stage >= node.resolveStage;

          return (
            <motion.div
              key={node.label}
              className={`absolute ${node.className} rounded-full border px-3 py-1.5 text-xs font-medium shadow-[0_10px_30px_rgba(0,0,0,0.24)]`}
              initial={reduceMotion ? false : { opacity: 0.42, scale: 0.96 }}
              animate={{
                opacity: resolved ? 1 : 0.42,
                scale: resolved ? 1 : 0.96,
                borderColor: resolved
                  ? "rgba(73,214,181,0.32)"
                  : "rgba(255,255,255,0.08)",
                backgroundColor: resolved
                  ? "rgba(17, 24, 30, 0.95)"
                  : "rgba(17, 21, 28, 0.70)",
                color: resolved ? "#F2F5F7" : "#8A93A3",
              }}
              transition={GRAPH.spring}
            >
              {node.label}
            </motion.div>
          );
        })}
      </div>
    </article>
  );
}

function RecordSkeleton() {
  return (
    <div className="space-y-4" aria-hidden="true">
      {[0, 1, 2, 3].map((row) => (
        <div key={row}>
          <div className="h-2 w-20 rounded-full bg-white/[0.08]" />
          <div className="mt-3 h-3 rounded-full bg-white/[0.06]" />
        </div>
      ))}
    </div>
  );
}

function DecisionRecordCard({
  stage,
  reduceMotion,
}: {
  stage: DemoStage;
  reduceMotion: boolean;
}) {
  const verified = stage >= STAGE.verified;
  const showRows = stage >= STAGE.recordRows;

  return (
    <motion.article
      className="relative z-10 rounded-xl border border-[rgba(var(--color-teal-rgb),0.22)] bg-[#10131A]/96 p-4 text-left shadow-[0_22px_70px_rgba(0,0,0,0.38)] backdrop-blur-md md:p-5"
      initial={reduceMotion ? false : { opacity: 0.58, x: RECORD.enterOffsetX, scale: 0.98 }}
      animate={{
        opacity: stage >= STAGE.sources ? 1 : 0.58,
        x: stage >= STAGE.verified ? 0 : RECORD.enterOffsetX,
        scale: stage >= STAGE.verified ? 1 : 0.98,
      }}
      transition={RECORD.spring}
    >
      <div className="mb-4 flex items-start justify-between gap-3 border-b border-white/[0.08] pb-4">
        <div>
          <p className="font-mono text-xs font-semibold text-[var(--color-teal)]">
            Decision Record
          </p>
          <p className="mt-1 text-xs leading-5 text-[#7A8494]">
            {verified ? "Verified from 5 sources" : "Waiting for source agreement..."}
          </p>
        </div>
        <motion.span
          className="inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] font-semibold"
          animate={{
            borderColor: verified
              ? "rgba(73,214,181,0.35)"
              : "rgba(255,255,255,0.08)",
            backgroundColor: verified
              ? "rgba(73,214,181,0.11)"
              : "rgba(255,255,255,0.035)",
            color: verified ? "var(--color-teal)" : "#7A8494",
            boxShadow:
              verified && !reduceMotion
                ? [
                    "0 0 0 rgba(73,214,181,0)",
                    "0 0 24px rgba(73,214,181,0.2)",
                    "0 0 0 rgba(73,214,181,0)",
                  ]
                : "0 0 0 rgba(73,214,181,0)",
          }}
          transition={{ duration: 1.8, repeat: verified ? Infinity : 0, ease: "easeInOut" }}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {verified ? "Verified" : "Waiting"}
        </motion.span>
      </div>

      {showRows ? (
        <div className="space-y-4">
          {RECORD.sections.map((section, index) => (
            <motion.section
              key={section.label}
              initial={reduceMotion ? false : { opacity: 0, y: RECORD.rowOffsetY }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                ...RECORD.spring,
                delay: reduceMotion ? 0 : index * RECORD.rowStagger,
              }}
            >
              <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6B7280]">
                {section.label}
              </h3>
              <div className="flex flex-wrap gap-2">
                {section.values.map((value) => (
                  <span
                    key={value}
                    className={
                      section.values.length === 1
                        ? "text-sm font-medium leading-6 text-[#F2F5F7]"
                        : "rounded-full border border-white/[0.08] bg-white/[0.045] px-2.5 py-1.5 text-xs font-medium text-[#D7DCE2]"
                    }
                  >
                    {value}
                  </span>
                ))}
              </div>
            </motion.section>
          ))}
        </div>
      ) : (
        <RecordSkeleton />
      )}
    </motion.article>
  );
}

export function DecisionGraphDemo() {
  const prefersReducedMotion = useReducedMotion();
  const reduceMotion = prefersReducedMotion === true;
  const { ref, inView } = useDemoInView();
  const stage = useDemoStage(reduceMotion, inView);

  return (
    <section
      aria-label="DecisionGraphDemo"
      className="relative mx-auto w-full rounded-2xl border border-white/[0.08] bg-[#06070B]/88 p-4 shadow-[0_30px_110px_rgba(0,0,0,0.5)] backdrop-blur-xl md:p-6"
      ref={ref}
    >
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-[linear-gradient(180deg,rgba(255,255,255,0.05),transparent_24%),linear-gradient(90deg,rgba(73,214,181,0.028),transparent_24%,transparent_76%,rgba(73,214,181,0.024))]" />

      <div className="relative z-10 mb-4 border-b border-white/[0.07] pb-4">
        <p className="font-mono text-xs font-semibold text-[var(--color-teal)]">
          Source matching
        </p>
        <p className="mt-1 text-xs text-[#6B7280]">
          Sources feed the graph until one decision becomes verified.
        </p>
      </div>

      <div className="relative grid gap-4 xl:min-h-[660px] xl:block">
        <FeedingStreams stage={stage} reduceMotion={reduceMotion} />
        <SourcePuckLayer stage={stage} reduceMotion={reduceMotion} />
        <KnowledgeGraphCore
          stage={stage}
          reduceMotion={reduceMotion}
          desktopTheater
        />
        <div className="relative z-10 xl:absolute xl:right-6 xl:top-1/2 xl:w-[360px] xl:-translate-y-1/2">
          <DecisionRecordCard stage={stage} reduceMotion={reduceMotion} />
        </div>
      </div>
    </section>
  );
}
