export function ChatSkeleton() {
  return (
    <div className="chat-skeleton" role="status" aria-label="Loading conversation">
      <div className="chat-skeleton-bubble chat-skeleton-bubble--user" />
      <div className="chat-skeleton-bubble chat-skeleton-bubble--assistant" />
      <div className="chat-skeleton-bubble chat-skeleton-bubble--user" />
    </div>
  );
}
