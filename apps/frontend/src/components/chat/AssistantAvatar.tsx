/** Assistant avatar — a document glyph in a tile (not a star/sparkle).
 *
 *  While a turn is in flight the tile switches to the brand fill and emits the
 *  `streaming-halo` pulse, so the "working" state is readable from the message
 *  column itself rather than only from the typing dots next to it. The halo is
 *  a box-shadow on the Root: `overflow-hidden` there clips children, not the
 *  element's own shadow, so it radiates correctly. */
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import { DocumentIcon } from './icons';

export function AssistantAvatar({ streaming = false }: { streaming?: boolean }) {
  return (
    <Avatar
      aria-hidden="true"
      className={cn('h-8 w-8 transition-all duration-300 ease-expo', streaming && 'streaming-halo')}
    >
      <AvatarFallback
        className={cn(
          'border-hairline transition-colors duration-300 ease-expo',
          streaming
            ? 'tile-sheen border-transparent bg-primary text-primary-foreground'
            : 'bg-card text-muted-foreground shadow-panel',
        )}
      >
        <DocumentIcon className="h-[17px] w-[17px]" />
      </AvatarFallback>
    </Avatar>
  );
}
