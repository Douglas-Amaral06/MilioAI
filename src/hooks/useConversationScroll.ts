import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { Conversation } from "../types";

const nearEnd = 64;
const showDistance = 160;

export function useConversationScroll(conversation?: Conversation) {
  const region = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLElement>(null);
  const followLatest = useRef(true);
  const returning = useRef(false);
  const frame = useRef<number | undefined>(undefined);
  const previous = useRef<{ id?: string; userId?: string }>({});
  const [away, setAway] = useState(false);
  const hasMessages = Boolean(conversation?.messages.length);
  const latestContent = conversation?.messages.at(-1)?.content;
  const latestUserId = conversation?.messages
    .filter((m) => m.role === "user")
    .at(-1)?.id;

  const measure = useCallback(() => {
    const element = region.current;
    if (!element) return;
    const distance =
      element.scrollHeight - element.clientHeight - element.scrollTop;
    if (distance <= nearEnd) returning.current = false;
    if (!returning.current) followLatest.current = distance <= nearEnd;
    setAway(distance > showDistance);
  }, []);

  const schedule = useCallback(() => {
    if (frame.current !== undefined) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = undefined;
      const element = region.current;
      if (element && followLatest.current && !returning.current)
        element.scrollTop = element.scrollHeight;
      measure();
    });
  }, [measure]);

  useLayoutEffect(() => {
    const element = region.current;
    const changed = previous.current.id !== conversation?.id;
    const sent =
      latestUserId !== undefined && previous.current.userId !== latestUserId;
    previous.current = { id: conversation?.id, userId: latestUserId };
    if (element && (changed || sent)) {
      returning.current = false;
      followLatest.current = true;
      element.scrollTop = element.scrollHeight;
      measure();
    } else schedule();
  }, [
    conversation?.id,
    conversation?.messages.length,
    latestUserId,
    latestContent,
    conversation?.supportState?.stage,
    conversation?.supportState?.vt_stage,
    measure,
    schedule,
  ]);

  useEffect(() => {
    const element = region.current;
    if (!element) return;
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    if (content.current) observer.observe(content.current);
    const interrupt = () => {
      returning.current = false;
      followLatest.current = false;
    };
    const interruptKey = (event: KeyboardEvent) => {
      if (
        [
          "ArrowUp",
          "ArrowDown",
          "PageUp",
          "PageDown",
          "Home",
          "End",
          " ",
        ].includes(event.key)
      )
        interrupt();
    };
    const finish = () => {
      if (returning.current) {
        returning.current = false;
        followLatest.current = true;
        schedule();
      }
    };
    element.addEventListener("wheel", interrupt, { passive: true });
    element.addEventListener("pointerdown", interrupt, { passive: true });
    element.addEventListener("keydown", interruptKey);
    element.addEventListener("scrollend", finish);
    return () => {
      observer.disconnect();
      element.removeEventListener("wheel", interrupt);
      element.removeEventListener("pointerdown", interrupt);
      element.removeEventListener("keydown", interruptKey);
      element.removeEventListener("scrollend", finish);
      if (frame.current !== undefined) cancelAnimationFrame(frame.current);
      frame.current = undefined;
    };
  }, [conversation?.id, hasMessages, schedule]);

  const goToLatest = () => {
    const element = region.current;
    if (!element) return;
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    returning.current = !reduceMotion;
    followLatest.current = true;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: reduceMotion ? "instant" : "smooth",
    });
    element.focus({ preventScroll: true });
    if (reduceMotion) measure();
  };
  return {
    region,
    content,
    onScroll: measure,
    goToLatest,
    showLatest: hasMessages && away,
  };
}
