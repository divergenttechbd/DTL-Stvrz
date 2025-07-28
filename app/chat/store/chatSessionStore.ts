import { create } from 'zustand'
import { Conversation, Message, PeerStatus } from '~/queries/models/conversation'

interface ChatSessionStore {
  conversations: Conversation[] | undefined
  conversationCount: number
  messages: {[key: string]: {data?: Message[]; updatedAt?: string}} | undefined
  peerStatus: {[key: string]: PeerStatus} | undefined
  typingStatus: {[key: string]: boolean} | undefined
  actions: {
    addConversation: (conversation: Conversation) => void
    addMessage: (conversationId: string, message: Message) => void
    updateMessage: (conversationId: string, messageId: string, data: Partial<Message>) => void
    updateLatestConversation: (data: Partial<Conversation>) => void
    updateLatestMessage: (conversationId: string, data: Partial<Message>) => void
    updateTypingStatus: (conversationId: string, status: boolean) => void
    updatePeerStatus: (userId: string, status: PeerStatus) => void
    reset: () => void
  }
}

const initialValue: {
  conversations: ChatSessionStore['conversations']
  messages: ChatSessionStore['messages']
  conversationCount: ChatSessionStore['conversationCount']
  typingStatus: ChatSessionStore['typingStatus']
} = {
  messages: undefined,
  conversationCount: 0,
  conversations: undefined,
  typingStatus: undefined
}

const useChatSessionStore = create<ChatSessionStore>((set, get) => {

  // console.log("--------------------------------", messages)

  return {
    conversations: undefined,
    messages: undefined,
    conversationCount: 0,
    peerStatus: undefined,
    typingStatus: undefined,
    actions: {
      addConversation: (conversation) => set({
        conversations: [...get().conversations || [], conversation],
        conversationCount: get().conversationCount + 1
      }),
      addMessage: (conversationId, message) => {
        set({
          messages: {
            ...get().messages,
            [conversationId]: {
              ...get().messages?.[conversationId],
              data: [...(get().messages?.[conversationId]?.data || []), message],
              updatedAt: message.created_at
            }
          }})
      },
      updateMessage: (conversationId, messageId, data) => {
        const messages = get().messages?.[conversationId]?.data
        const messageIndex = messages?.findIndex(i => i.id === messageId) ?? -1
        if ((messageIndex >= 0) && messages?.length) {
          messages[messageIndex] = {
            ...messages[messageIndex],
            ...data
          }
        }
        set({messages: {
          ...get().messages,
          [conversationId]: {
            ...get().messages?.[conversationId],
            data: messages?.length ? [...messages] : undefined
          }
        }})
      },
      updateLatestConversation: (data) => {
        const conversations = get().conversations
        if (conversations?.length) {
          conversations[conversations.length - 1] = {
            ...conversations[conversations.length - 1],
            ...data
          }
          set({conversations})
        }
      },
      updateLatestMessage: (conversationId, data) => {
        const messages = get().messages?.[conversationId]?.data
        if (messages?.length) {
          messages[messages.length - 1] = {
            ...messages[messages.length - 1],
            ...data
          }
        }
        set({
          messages: {
            ...get().messages,
            [conversationId]: {
              ...get().messages?.[conversationId],
              data: messages?.length ? [...messages] : undefined
            }
          }})
      },
      updateTypingStatus: (conversationId, status) => set({typingStatus: {
        ...get().typingStatus,
        [conversationId]: status
      }}),
      updatePeerStatus: (userId, status) => set({peerStatus: {
        ...get().peerStatus,
        [userId]: {
          ...get().peerStatus?.[userId],
          ...status
        }
      }}),
      reset: () => {
        set({...initialValue})
      }
    }
  }
})

export const useChatSessionConversations = () => useChatSessionStore(state => state.conversations)
export const useChatSessionMessages = () => useChatSessionStore(state => state.messages)
export const useChatSessionTypingStatus = () => useChatSessionStore(state => state.typingStatus)
export const useChatSessionActions = () => useChatSessionStore(state => state.actions)
export const useChatSessionConversationMessages = (id: string) => useChatSessionStore(state => state.messages?.[id]?.data)
export const useChatSessionConversationTypingStatus = (id: string) => useChatSessionStore(state => state.typingStatus?.[id])
export const useChatSessionPeerStatus = (id?: string) => useChatSessionStore(state => id ? state.peerStatus?.[id] : undefined)
export const useChatSessionNewConversationCount = () => useChatSessionStore(state => state.conversationCount)
