import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatSessionActions } from '~/app/chat/store/chatSessionStore'
import { ConnectionStatus } from '~/app/chat/types'
import { getToken } from '~/lib/storage/token'
import { Conversation, Message } from '~/queries/models/conversation'

interface UseChatSessionArgs {
  canConnect?: boolean
  userId?: string
}

export const useChatSession = (args?: UseChatSessionArgs) => {
  const { canConnect, userId } = args || {}
  const { addMessage, updateMessage, addConversation, updateTypingStatus, updateLatestMessage, updatePeerStatus } = useChatSessionActions()
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('CONNECTING')
  const sessionRef = useRef<WebSocket>()
  const token = getToken()
  useEffect(() => {
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/user-global-room/?token=${token}}`) //API User Global Room

    const keepAliveInterval = setInterval(() => {
      if(ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    ws.onclose = () => {
      clearInterval(keepAliveInterval)
    }

    return () => {
      clearInterval(keepAliveInterval)
      ws.close()
    }
  }, [])

  const handleConnectionOpen: WebSocket['onopen'] = useCallback(() => {
    setConnectionStatus('OPEN')
  }, [])

  const handleConnectionClose: WebSocket['onclose'] = useCallback((e: CloseEvent) => {
    console.log('websocket closed', e)
    setConnectionStatus(e.reason === 'EXIT' ? 'EXIT' : 'CLOSED')
  }, [])

  const handleConnectionError: WebSocket['onerror'] = useCallback(() => {
    setConnectionStatus('ERROR')
  }, [])

  const listenConnectionChange = useCallback((session: WebSocket) => {
    if(!session) return
    session.addEventListener('open', handleConnectionOpen)
    session.addEventListener('close', handleConnectionClose)
    session.addEventListener('error', handleConnectionError)
  }, [handleConnectionOpen, handleConnectionClose, handleConnectionError])

  const handleSaveMessage = useCallback(({
    conversationId,
    ...message
  }: Message & { conversationId: Conversation['id'] }) => {
    addMessage(conversationId, message)
  }, [addMessage])

  const listenMessageReceive = useCallback((session: WebSocket) => {
    if(!session) return
    session.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if(data.action === 'join') updatePeerStatus(data.user_id, { online_status: true })
      if(data.action === 'leave') updatePeerStatus(data.user_id, { online_status: false, last_online: data.last_online })
      if(data.action === 'is_typing') updateTypingStatus(data.conversationId, data.status)
      if(data.action === 'message') {
        if(data.retryMessageId && (data.user.user_id === userId)) {
          updateMessage(data.conversationId, data.retryMessageId, {
            id: data.id,
            created_at: data.created_at,
            is_failed: false,
          })
        } else {
          handleSaveMessage({
            id: data.id,
            conversationId: data.room.id,
            user: data.user,
            content: data.message,
            created_at: data.created_at,
            is_read: false,
            m_type: 'normal',
          })
        }
      }
      if(data.action === 'read_done') updateLatestMessage(data.room_id, { is_read: true })
      if(((data.action_type === 'inquiry') || (data.action_type === 'confirmed')) && Array.isArray(data.messages)) {
        const chatRoom = data.messages[data.messages.length - 1].chat_room
        const conversation: Conversation = {
          id: chatRoom.id,
          from_user: {
            id: chatRoom.from_user.id,
            user_id: chatRoom.from_user.user_id,
            username: chatRoom.from_user.username,
            email: chatRoom.from_user.email,
            full_name: chatRoom.from_user.full_name,
            image: chatRoom.from_user.image,
          },
          to_user: {
            id: chatRoom.to_user.id,
            user_id: chatRoom.to_user.user_id,
            username: chatRoom.to_user.username,
            email: chatRoom.to_user.email,
            full_name: chatRoom.to_user.full_name,
            image: chatRoom.to_user.image,
          },
          latest_message: {
            id: chatRoom.latest_message.id,
            content: chatRoom.latest_message.content,
            created_at: chatRoom.created_at,
            user: {
              id: chatRoom.from_user.id,
              user_id: chatRoom.from_user.user_id,
              username: chatRoom.from_user.username,
              email: chatRoom.from_user.email,
              full_name: chatRoom.from_user.full_name,
              image: chatRoom.from_user.image,
            },
            is_read: false,
            m_type: chatRoom.latest_message.m_type,
          },
          name: chatRoom.name,
          status: chatRoom.updated_at,
          updated_at: chatRoom.updated_at,
          listing: chatRoom.updated_at,
          booking_data: chatRoom.updated_at,
        }
        data.messages.forEach((item: any) => {
          handleSaveMessage({
            id: item.id,
            conversationId: conversation.id,
            user: {
              id: item.user.id,
              user_id: item.user.user_id,
              username: item.user.username,
              email: item.user.email,
              full_name: item.user.full_name,
              image: item.user.image,
            },
            content: item.content,
            created_at: item.created_at,
            is_read: false,
            m_type: item.m_type,
            meta: item.meta
          })
        })
        if(data.is_new_chatroom) addConversation(conversation)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleSaveMessage, updateTypingStatus, updateLatestMessage, addConversation, updateMessage, userId])

  const reset = useCallback(() => {
    sessionRef.current?.close(1000, 'EXIT')
    sessionRef.current?.removeEventListener('open', handleConnectionOpen)
    sessionRef.current?.removeEventListener('close', handleConnectionClose)
    sessionRef.current?.removeEventListener('error', handleConnectionError)
    sessionRef.current = undefined
    setConnectionStatus('CONNECTING')
  }, [handleConnectionOpen, handleConnectionClose, handleConnectionError])

  const connectSession = useCallback(() => {
    reset()
    sessionRef.current = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/user-global-room/?token=${token}`) //API User Global Room
    listenConnectionChange(sessionRef.current)
    listenMessageReceive(sessionRef.current)
  }, [reset, listenConnectionChange, listenMessageReceive])

  useEffect(() => {
    if((typeof canConnect === 'boolean') && !canConnect) return
    connectSession()
    const session = sessionRef.current
    return () => session?.close(1000, 'EXIT')
  }, [connectSession, canConnect])

  return { connectionStatus, connectSession }
}
