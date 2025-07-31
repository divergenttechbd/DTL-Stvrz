import { useEffect, useCallback, useState } from 'react';
// @mui
import Card from '@mui/material/Card';
import Stack from '@mui/material/Stack';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
// routes
import { paths } from 'src/routes/paths';
import { useRouter, useSearchParams } from 'src/routes/hook';
// api
import { useGetContacts, useGetConversation, useGetConversations } from 'src/api/chat';
// components
import { useSettingsContext } from 'src/components/settings';
// types
import { IChatRecepient } from 'src/types/chat';
import { useBoolean } from 'src/hooks/use-boolean';

import { ConfirmDialog } from 'src/components/custom-dialog';
import { Button } from '@mui/material';
import { IBookingItem } from 'src/types/booking';
//
import ChatNav from '../chat-nav';
import ChatMessageList from '../chat-message-list';
import ChatMessageInput from '../chat-message-input';
import ChatHeaderDetail from '../chat-header-detail';
import ChatRoom from '../chat-room';

// ----------------------------------------------------------------------

export default function ChatView() {
  const router = useRouter();

  const settings = useSettingsContext();

  const searchParams = useSearchParams();
  const showDetails = useBoolean();

  const selectedConversationId = searchParams.get('id') || '';

  const [chatDetails, setChatDetails] = useState<IBookingItem | null>();

  const { contacts } = useGetContacts();
  const { conversationsLoading } = useGetConversations();

  const { conversation, conversationError, chatroom, refetchConversation, conversationValidating } =
    useGetConversation(`${selectedConversationId}`);

  const recipients = chatroom ? [chatroom.from_user, chatroom.to_user] : [];

  // console.log("---------- recipients", chatroom)

  useEffect(() => {
    if(conversationError || !selectedConversationId) {
      router.push(paths.dashboard.chat);
    }
  }, [conversationError, router, selectedConversationId]);

  const handleAddRecipients = useCallback((selected: IChatRecepient[]) => { }, []);

  const details = !!conversation && chatroom;

  const renderHead = (
    <Stack
      direction="row"
      alignItems="center"
      flexShrink={0}
      sx={{ pr: 1, pl: 2.5, py: 1, minHeight: 72 }}
    >
      {details && (
        <ChatHeaderDetail
          chatroom={chatroom}
          participants={recipients}
          id={selectedConversationId}
          refetchConversation={refetchConversation}
        />
      )}
    </Stack>
  );

  const renderNav = (
    <ChatNav
      contacts={contacts}
      loading={conversationsLoading}
      selectedConversationId={selectedConversationId}
    />
  );

  const renderMessages = (
    <Stack
      sx={{
        width: 1,
        height: 1,
        overflow: 'hidden',
      }}
    >
      <ChatMessageList
        messages={conversation}
        loading={conversationValidating}
        setChatDetails={setChatDetails}
        showDetails={showDetails}
      />

      <ChatMessageInput
        recipients={[chatroom?.from_user, chatroom?.to_user]}
        onAddRecipients={handleAddRecipients}
        //
        selectedConversationId={selectedConversationId}
        disabled
      />
    </Stack>
  );

  return (
    <Container maxWidth={settings.themeStretch ? false : 'xl'}>
      <Typography
        variant="h4"
        sx={{
          mb: { xs: 3, md: 5 },
        }}
      >
        Chat
      </Typography>

      <Stack component={Card} direction="row" sx={{ height: '72vh' }}>
        {renderNav}

        <Stack
          sx={{
            width: 1,
            height: 1,
            overflow: 'hidden',
          }}
        >
          {renderHead}

          <Stack
            direction="row"
            sx={{
              width: 1,
              height: 1,
              overflow: 'hidden',
              borderTop: (theme) => `solid 1px ${theme.palette.divider}`,
            }}
          >
            {renderMessages}

            {/* {details && <ChatRoom conversation={chatDetails} />} */}

            <ConfirmDialog
              open={showDetails.value}
              onClose={showDetails.onFalse}
              title="Chat Details"
              content={
                <>
                  {details && (
                    <ChatRoom
                      booking={chatDetails}
                      user={chatroom.from_user}
                      listing={chatroom.listing}
                    />
                  )}
                </>
              }
              // eslint-disable-next-line react/jsx-no-useless-fragment
              action={<></>}
            />
          </Stack>
        </Stack>
      </Stack>
    </Container>
  );
}
