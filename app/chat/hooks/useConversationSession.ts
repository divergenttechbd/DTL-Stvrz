import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatSessionActions } from '~/app/chat/store/chatSessionStore'
import { ConnectionStatus } from '~/app/chat/types'
import { getToken } from '~/lib/storage/token'
import { getUUID } from '~/lib/utils/uuid'
import { Message } from '~/queries/models/conversation'

export interface UseChatSessionArgs {
  conversationId: string
  sender?: any
}

export const useConversationSession = ({
  conversationId,
  sender,
}: UseChatSessionArgs) => {
  const { addMessage } = useChatSessionActions()
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('CONNECTING')
  const sessionRef = useRef<WebSocket>()
  const token = getToken()
  const handleSendTypingStatus = useCallback((status: boolean) => {
    if (sessionRef.current?.readyState !== 1) return
    if (!conversationId) return
    sessionRef.current?.send(JSON.stringify({ action: 'is_typing', status, conversationId}))
  }, [conversationId])

  const handleMessageSendFailure = useCallback((content: string) => {
    if (!sender) return
    const message: Message = {
      id: getUUID(),
      user: sender,
      content: content,
      created_at: (new Date).toISOString(),
      is_read: false,
      m_type: 'normal',
      is_failed: true,
    }
    addMessage(conversationId, message)
  }, [conversationId, sender, addMessage])
  
  const handleSendMessage: WebSocket['send'] = useCallback((data) => {
    if (sessionRef.current?.readyState !== 1) return
    const message = data.toString()
    handleSendTypingStatus(false)
    try {
      sessionRef.current?.send(JSON.stringify({ action: 'message', message }))
    } catch (error) {
      handleMessageSendFailure(message)
    }
  }, [handleSendTypingStatus, handleMessageSendFailure])

  const handleRetryMessageSend = useCallback((conversationId: string, message: Message) => {
    if (sessionRef.current?.readyState !== 1) return
    sessionRef.current?.send(JSON.stringify({ action: 'message', message: message.content, conversationId, retryMessageId: message.id }))
  }, [])

  const handleSendReadStatus = useCallback(() => {
    if (sessionRef.current?.readyState !== 1) return
    sessionRef.current?.send(JSON.stringify({ action: 'is_read' }))
  }, [])

  const handleSendInquiryMessage = useCallback(() => {
    if (sessionRef.current?.readyState !== 1) return
    sessionRef.current?.send(JSON.stringify({ action: 'inquiry' }))
  }, [])

  const handleSendConfirmationMessage = useCallback(() => {
    if (sessionRef.current?.readyState !== 1) return
    sessionRef.current?.send(JSON.stringify({ action: 'confirmed' }))
  }, [])

  const handleConnectionOpen: WebSocket['onopen'] = useCallback(() => {
    setConnectionStatus('OPEN')
  }, [])

  const handleConnectionClose: WebSocket['onclose']  = useCallback((e: CloseEvent) => {
    console.log('websocket closed', e)
    setConnectionStatus(e.reason === 'EXIT' ? 'EXIT' : 'CLOSED')
  }, [])

  const handleConnectionError: WebSocket['onerror']  = useCallback(() => {
    setConnectionStatus('ERROR')
  }, [])

  const listenConnectionChange = useCallback((session: WebSocket) => {
    if (!session) return
    session.addEventListener('open', handleConnectionOpen)
    session.addEventListener('close', handleConnectionClose)
    session.addEventListener('error', handleConnectionError)
  }, [handleConnectionOpen, handleConnectionClose, handleConnectionError])

  const reset = useCallback(() => {
    sessionRef.current?.close(1000, 'EXIT')
    sessionRef.current?.removeEventListener('open', handleConnectionOpen)
    sessionRef.current?.removeEventListener('close', handleConnectionClose)
    sessionRef.current?.removeEventListener('error', handleConnectionError)
    sessionRef.current = undefined
    setConnectionStatus('CONNECTING')
  }, [handleConnectionOpen, handleConnectionClose, handleConnectionError])

  const connectSession = useCallback(() => {
    if (!conversationId) return
    reset()
    sessionRef.current = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/${conversationId}/?token=${token}`) //API Conversation
    listenConnectionChange(sessionRef.current)
  }, [conversationId, reset, listenConnectionChange])

  useEffect(() => {
    connectSession()
    const session = sessionRef.current
    return () => session?.close(1000, 'EXIT')
  }, [connectSession])

  return {
    connectionStatus,
    connectSession,
    sendMessage: handleSendMessage,
    retryMessageSend: handleRetryMessageSend,
    sendReadStatus: handleSendReadStatus,
    sendInquiryMessage: handleSendInquiryMessage,
    sendConfirmationMessage: handleSendConfirmationMessage,
    sendTypingStatus: handleSendTypingStatus,
  }
}
