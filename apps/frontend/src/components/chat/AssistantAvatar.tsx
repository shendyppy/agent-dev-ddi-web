/** Assistant avatar — a document glyph in a muted tile (not a star/sparkle). */
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { DocumentIcon } from './icons';

export function AssistantAvatar() {
  return (
    <Avatar aria-hidden="true">
      <AvatarFallback>
        <DocumentIcon className="h-[18px] w-[18px]" />
      </AvatarFallback>
    </Avatar>
  );
}
