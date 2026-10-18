import type { Comment, User } from "@/api/types";
import { useComments } from "@/features/tickets/api";
import styles from "@/features/tickets/Conversation.module.css";
import { formatDateTime, formatRelative } from "@/lib/format";
import { Button } from "@/ui/Button";
import { classNames } from "@/ui/class-names";

export function Conversation({ ticketId, viewer }: { ticketId: string; viewer: User }) {
  const comments = useComments(ticketId);

  if (comments.isPending) {
    return (
      <p className={styles.state} role="status">
        Loading the conversation…
      </p>
    );
  }
  if (comments.isError) {
    return (
      <div className={styles.state}>
        <p>Couldn't load the conversation.</p>
        <Button size="sm" onClick={() => void comments.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <section aria-labelledby="conversation-heading" className={styles.conversation}>
      <h2 id="conversation-heading" className={styles.heading}>
        Conversation
      </h2>
      {comments.data.length === 0 ? (
        <p className={styles.state}>No replies yet.</p>
      ) : (
        <ol className={styles.thread}>
          {comments.data.map((comment) => (
            <li key={comment.id}>
              <CommentEntry comment={comment} viewer={viewer} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function CommentEntry({ comment, viewer }: { comment: Comment; viewer: User }) {
  const { author } = comment;
  const isViewer = author.id === viewer.id;
  const isInternal = comment.visibility === "internal";

  return (
    <article className={classNames(styles.comment, isInternal && styles.internal)}>
      <header className={styles.meta}>
        <span className={styles.author}>{isViewer ? "You" : author.display_name}</span>
        {author.role !== "customer" && !isViewer && <span className={styles.tag}>Support</span>}
        {isInternal && <span className={styles.tag}>Internal note</span>}
        <time
          dateTime={comment.created_at}
          title={formatDateTime(comment.created_at)}
          className={styles.time}
        >
          {formatRelative(comment.created_at)}
        </time>
      </header>
      <p className={styles.body}>{comment.body}</p>
    </article>
  );
}
