// @mui
import Stack from '@mui/material/Stack';
import Badge from '@mui/material/Badge';
import Avatar from '@mui/material/Avatar';
import IconButton from '@mui/material/IconButton';
import AvatarGroup, { avatarGroupClasses } from '@mui/material/AvatarGroup';
// types
import { IChatConversation, IChatMessage, IChatRecepient } from 'src/types/chat';
// components
import Iconify from 'src/components/iconify';
import { useCallback } from 'react';
import { FormControlLabel, Link, Switch, ToggleButton, Typography } from '@mui/material';
import { paths } from 'src/routes/paths';
import { updateRestriction } from 'src/utils/queries/chat';

// ----------------------------------------------------------------------

type Props = {
  participants: any;
  id: string;
  chatroom: IChatConversation;
  refetchConversation: Function;
};

export default function ChatHeaderDetail({
  participants,
  id,
  chatroom,
  refetchConversation,
}: Props) {

  const group = participants.length > 1;

  const singleParticipant = participants[0];
  const singleMutipleParticipant = participants[1];

  const handleRefresh = useCallback(() => {
    refetchConversation();
  }, [refetchConversation]);

  const toggleRestriction = useCallback(async () => {
    try {
      const res = await updateRestriction({
        id,
        status: chatroom?.status === 'closed' ? 'open' : 'closed',
      });
      if(!res.success) throw res.data;
      refetchConversation();
    } catch(err) {
      console.log(err);
    }
  }, [refetchConversation, id, chatroom]);

  const renderGroup = (
    <Stack direction="row" alignItems="center">
      <AvatarGroup
        max={3}
        sx={{
          [`& .${avatarGroupClasses.avatar}`]: {
            width: 32,
            height: 32,
          },

        }}
      >

        <Link color="inherit" sx={{ backgroundColor: 'transparent !important' }} href={`${paths.dashboard.user.root}/${singleParticipant?.user_id}/edit`} target="_blank">
          <Avatar key={singleParticipant.id} alt={singleParticipant.full_name} src={singleParticipant.image} />
        </Link>

        {Array.isArray(singleMutipleParticipant) ? (
          singleMutipleParticipant.length > 0 &&
          singleMutipleParticipant.map((participant: any) => (
            <Link
              color="inherit"
              sx={{ backgroundColor: 'transparent !important' }}
              href={`${paths.dashboard.user.root}/${participant?.user_id}/edit`}
              target="_blank"
              key={participant.id}
            >
              <Avatar alt={participant.full_name} src={participant.image} />
            </Link>
          ))
        ) : (
          singleMutipleParticipant && (
            <Link
              color="inherit"
              sx={{ backgroundColor: 'transparent !important' }}
              href={`${paths.dashboard.user.root}/${singleMutipleParticipant?.user_id}/edit`}
              target="_blank"
              key={singleMutipleParticipant.id}
            >
              <Avatar alt={singleMutipleParticipant.full_name} src={singleMutipleParticipant.image} />
            </Link>
          )
        )}


      </AvatarGroup>

      <Typography variant="subtitle2" marginLeft={2}>
        {singleParticipant.username} {singleParticipant.username.endsWith('host') ? '(Host) ' : '(Guest) '},
        {singleMutipleParticipant.length ?
          <>
            {singleMutipleParticipant
              .map(
                (participant: any) =>
                  `${participant.full_name} ${participant.username.endsWith('host') ? '(Host) ' : '(Guest) '
                  }`
              )
              .join(', ')}
          </> :
          <>
            {singleMutipleParticipant.username} {singleMutipleParticipant.username.endsWith('host') ? '(Host) ' : '(Guest) '}
          </>

        }
      </Typography>
    </Stack >
  );

  const renderSingle = (
    <Stack flexGrow={1} direction="row" alignItems="center" spacing={2}>
      <Badge anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Avatar src={singleParticipant.image} alt={singleParticipant.full_name} />
      </Badge>
    </Stack>
  );

  return (
    <>
      {group ? renderGroup : renderSingle}

      <Stack flexGrow={1} />

      <FormControlLabel
        label="Restricted"
        control={<Switch checked={chatroom?.status === 'closed'} onChange={toggleRestriction} />}
        sx={{}}
      />

      <IconButton onClick={handleRefresh}>
        <Iconify icon="eva:refresh-outline" />
      </IconButton>
    </>
  );
}
