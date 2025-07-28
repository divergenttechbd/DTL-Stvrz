import { FC } from 'react'
import { Virtuoso } from 'react-virtuoso'
import { type Conversation as ConversationData } from '~/queries/models/conversation'
import { Conversation } from '~/app/chat/components/conversationList/Conversation'

interface ConversationsProps {
  data: ConversationData[]
  activeConversationId?: string
  visitedConversations?: string[]
}

export const Conversations: FC<ConversationsProps> = ({
  data,
  activeConversationId,
  visitedConversations,
}) => {

  // console.log("next step data -------------------", data)

  return (
    <Virtuoso
      data={data}
      itemContent={(_, conversation) => (
        <div className='mx-5 md:mx-3 py-[1px]'>
          <Conversation data={conversation} isActive={activeConversationId === conversation.id} isVisited={visitedConversations?.includes(conversation.id)} />
        </div>
      )}
    />
  )
}
