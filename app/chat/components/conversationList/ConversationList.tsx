'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter, useSearchParams } from 'next/navigation'
import { FC, useEffect, useMemo, useState } from 'react'
import { Header } from '~/app/chat/components/conversationList/Header'
// import { SearchInbox } from '~/app/chat/components/conversationList/SearchInbox'
import { useMergedConversations } from '~/app/chat//hooks/useMergedConversations'
import { Conversations } from '~/app/chat/components/conversationList/Conversations'
import { useChatSessionMessages } from '~/app/chat/store/chatSessionStore'
import Loader from '~/components/loader/Loader'
import { parseDate } from '~/lib/utils/formatter/dateFormatter'
import { getConversations } from '~/queries/client/conversation'

interface ConversationListProps {
  className?: string
  isMobileView?: boolean
}

export const ConversationList: FC<ConversationListProps> = ({
  className = '',
  isMobileView,
}) => {
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeConversationId = searchParams.get('conversation_id')
  const messageType = searchParams.get('message_type')
  const messages = useChatSessionMessages()
  const [visitedConversations, setVisitedConversations] = useState<string[]>([])

  const { data, isFetching } = useQuery({
    queryKey: ['conversationList'],
    queryFn: () => getConversations(),
    refetchOnWindowFocus: false
  })

  // console.log("api call data-----------------", data)

  const { conversations } = useMergedConversations({ fetchedConversations: data?.data })
  // console.log("conversations data-----------------", conversations)
  const sortedConversations = useMemo(() => {
    const data = conversations?.map(i => ({ ...i, updated_at: parseDate(messages?.[i.id]?.updatedAt || i.updated_at).toISOString() }))
    return data?.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  }, [messages, conversations])

  // console.log("conversations data-----------------", sortedConversations)

  // Make first one the selected conversation
  useEffect(() => {
    if(!sortedConversations || activeConversationId) return
    const firstConversation = sortedConversations[0]
    if(!isMobileView && firstConversation) router.replace(`?conversation_id=${firstConversation.id}`)
  }, [sortedConversations, router, activeConversationId, isMobileView])

  // Save visited conversations
  useEffect(() => {
    if(activeConversationId && !visitedConversations.includes(activeConversationId)) setVisitedConversations(prevValue => ([...prevValue, activeConversationId]))
  }, [activeConversationId, visitedConversations])

  return (
    <div className={`flex grow flex-col max-sm:fixed max-sm:inset-0 md:border-r-2 ${className}`}>
      {isFetching ? <Loader className='mt-20' /> : sortedConversations ? <>
        <Header title={messageType === 'bdbnb_support' ? 'Stayverz Support' : 'All messages'} allMessageCount={conversations?.length || 0} />
        {/* <SearchInbox /> */}
        {sortedConversations ? <Conversations data={sortedConversations} activeConversationId={activeConversationId ?? undefined} visitedConversations={visitedConversations} /> : null}
      </> : 'Empty'}
    </div>
  )
}
