import React, { useCallback } from 'react';
import { format, formatDistanceToNowStrict } from 'date-fns';
// @mui
import Stack from '@mui/material/Stack';
import Badge from '@mui/material/Badge';
import Avatar from '@mui/material/Avatar';
import Typography from '@mui/material/Typography';
import AvatarGroup from '@mui/material/AvatarGroup';
import ListItemText from '@mui/material/ListItemText';
import ListItemButton from '@mui/material/ListItemButton';
// routes
import { paths } from 'src/routes/paths';
import { useRouter } from 'src/routes/hook';
// hooks
import { useMockedUser } from 'src/hooks/use-mocked-user';
import { useResponsive } from 'src/hooks/use-responsive';
// types
import { IChatConversation } from 'src/types/chat';
//
import { useGetNavItem } from './hooks';


// ----------------------------------------------------------------------

type Props = {
  selected: boolean;
  collapse: boolean;
  onCloseMobile: VoidFunction;
  conversation: IChatConversation;
};

export default function ChatNavItem({ selected, collapse, conversation, onCloseMobile }: Props) {

  const { user } = useMockedUser();
  const mdUp = useResponsive('up', 'md');
  const router = useRouter();

  const { displayName, displayText, participants, lastActivity, hasOnlineInGroup } = useGetNavItem({
    conversation,
    currentUserId: user.id,
  });

  const singleParticipant = participants[0];
  const singleMutipleParticipant = participants[1];

  const handleClickConversation = useCallback(async () => {
    try {
      if(!mdUp) {
        onCloseMobile();
      }

      router.push(`${paths.dashboard.chat}?id=${conversation.id}`);
    } catch(error) {
      console.error(error);
    }
  }, [conversation.id, mdUp, onCloseMobile, router]);

  const renderGroup = (
    <Badge
      variant={hasOnlineInGroup ? 'online' : 'invisible'}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    >
      <AvatarGroup variant="compact" sx={{ width: 48, height: 48 }}>
        {singleMutipleParticipant.length > 0 &&
          singleMutipleParticipant.map((participant: any) => (
            <Avatar key={participant?.id} alt={participant?.full_name} src={participant?.image} />
          ))}
        <Avatar alt={singleParticipant?.full_name} src={singleParticipant?.image} />
        <Avatar alt={singleMutipleParticipant?.full_name} src={singleMutipleParticipant?.image} />
      </AvatarGroup>
    </Badge>
  );

  return (
    <ListItemButton
      disableGutters
      onClick={handleClickConversation}
      sx={{
        py: 1.5,
        px: 2.5,
        ...(selected && {
          bgcolor: 'action.selected',
        }),
      }}
    >
      <Badge color="error" overlap="circular">
        {renderGroup}
      </Badge>

      {!collapse && (
        <>
          <ListItemText
            sx={{ ml: 2 }}
            primary={displayName}
            primaryTypographyProps={{
              noWrap: true,
              variant: 'subtitle2',
            }}
            secondary={displayText}
            secondaryTypographyProps={{
              noWrap: true,
              component: 'span',
              variant: 'body2',
              color: 'text.secondary',
            }}
          />

          <Stack alignItems="flex-end" sx={{ ml: 2, height: 44 }}>
            <Typography
              noWrap
              variant="body2"
              component="span"
              sx={{
                mb: 1.5,
                fontSize: 12,
                color: 'text.disabled',
              }}
            >
              {format(new Date(lastActivity), 'MMM dd')}
            </Typography>

            {/* {!!conversation.unreadCount && (
              <Box sx={{ width: 8, height: 8, bgcolor: 'info.main', borderRadius: '50%' }} />
            )} */}
          </Stack>
        </>
      )}
    </ListItemButton>
  );
}
