// types
import { IChatConversation } from 'src/types/chat';

// ----------------------------------------------------------------------

type Props = {
  currentUserId: string;
  conversation: any;
};

export default function useGetNavItem({ currentUserId, conversation }: Props) {

  // console.log("inside conversation", conversation.latest_message)

  const group = true;

  const displayName = `${conversation?.from_user?.full_name}, ${conversation.to_user?.length ? `${conversation.to_user[0]?.full_name}, ${conversation.to_user[1]?.full_name}` : conversation.to_user?.full_name}`;

  const displayText = `${conversation?.latest_message?.user?.full_name || 'Admin'}: ${conversation.latest_message.content}`;

  return {
    group,
    displayName,
    displayText,
    participants: [conversation.from_user, conversation.to_user],
    lastActivity: conversation.updated_at,
    hasOnlineInGroup: false,
  };
}
