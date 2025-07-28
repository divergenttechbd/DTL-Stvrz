export type ConverstationStatus = 'inquiry' | 'confirmed' | 'cancelled'

export interface Conversation {
  id: string
  from_user: any
  to_user: any
  status: ConverstationStatus
  booking_data: {
    check_in: string
    check_out: string
    total_guest_count: number
  }
  listing: {
    id: string
    name: string
  }
  name: string
  latest_message: Message
  updated_at: string
}

export interface Message {
  id?: string
  content: string
  user: Peer
  created_at: string
  m_type?: 'normal' | 'system'
  is_read?: boolean
  meta?: {
    booking: { [key: string]: any }
    listing: string
    user: string
  }
  is_failed?: boolean
}

export interface ConversationDetails {
  extra_data: {
    chat_room: Conversation
  }
  data: Message[]
}

export interface Peer extends PeerStatus {
  id: string
  user_id: string
  username: string
  image: string
  email: string
  full_name: string
}

export interface PeerStatus {
  online_status?: boolean
  last_online?: string
}
