import { ArrowBendUpLeft } from '@phosphor-icons/react'
import Link from 'next/link'
import React from 'react'
import { FC, useMemo } from 'react'
import { DATE_FORMAT } from '~/app/chat/constants'
import { useSenderReceiver } from '~/app/chat/hooks/useSenderReceiver'
import { useChatSessionConversationMessages } from '~/app/chat/store/chatSessionStore'
import { UserAvatar } from '~/components/layout/UserAvatar'
import { formatDate, formatTime } from '~/lib/utils/formatter/dateFormatter'
import { ConverstationStatus, type Conversation as ConversationData } from '~/queries/models/conversation'
import Cookie from 'js-cookie'


export interface ConversationProps {
  data: ConversationData
  isActive?: boolean
  isVisited?: boolean
}

export const Conversation: FC<ConversationProps> = ({
  data,
  isActive,
  isVisited,
}) => {
  const host_guest_user_id = Cookie.get('host_guest_user_id')
  const { id, to_user, from_user, listing, booking_data, latest_message, status } = data
  const { sender, receiver } = useSenderReceiver({ fromUser: from_user, toUser: to_user })
  const sessionMessages = useChatSessionConversationMessages(data.id)
  const { user, content, created_at, m_type, is_read } = sessionMessages?.[sessionMessages?.length - 1] || latest_message
  const duration = useMemo(() => (`${formatDate(booking_data.check_in, 'MMM D')} - ${formatDate(booking_data.check_out, 'MMM D')}`), [booking_data])
  const isRead = (!sessionMessages?.length && isVisited) || (user.user_id === sender?.user_id) || is_read
  const formattedDate = useMemo(() => {
    return formatDate(new Date().toISOString(), DATE_FORMAT) === formatDate(created_at, DATE_FORMAT) ? formatTime(created_at) : formatDate(created_at, 'MMM DD')
  }, [created_at])
  if(!sender || !receiver) return null

  // console.log('coversation data----------------', data)
  // console.log('sender.user_id----------------', sender.user_id)
  // console.log('receiver.user_id----------------', receiver.user_id)
  // console.log('to_user----------------', to_user)
  // console.log('from_user----------------', from_user)

  // console.log('sender', sender)
  // console.log('receiver', receiver)
  // console.log('sender', sender.length > 0 ? "Siam" : "TAnvir")

  const parsedFuncton = () => {
    let parsedContent
    try {
      if(content.trim().startsWith('{')) {
        parsedContent = JSON.parse(content.replace(/'/g, '"'))
      }
    } catch(e) {
      parsedContent = content
    }

    return parsedContent
  }

  const parsedData = parsedFuncton()

  return (
    <Link href={`?conversation_id=${id}`}>
      <div className={`flex items-center gap-2 max-sm:px-2 sm:px-4 py-4 ${isActive ? 'bg-gray-100 rounded-lg' : 'border-b'}`}>

        <div className='relative w-10 h-10 mr-5'>

          {to_user.length ?
            <React.Fragment>

              <div className='absolute top-3 left-0'>
                <div className='shrink-0 w-8 h-8 relative'>
                  <UserAvatar
                    image={
                      receiver.length > 0
                        ? receiver
                          .filter((r: any) => r.user_id !== Number(host_guest_user_id))
                          .map((r: any) => r.image)
                          .join(', ')
                        : receiver.user_id !== Number(host_guest_user_id) ? receiver.image : ''
                    }
                    fullName={
                      receiver.length > 0
                        ? receiver
                          .filter((r: any) => r.user_id !== Number(host_guest_user_id))
                          .map((r: any) => r.full_name)
                          .join(', ')
                        : receiver.user_id !== Number(host_guest_user_id) ? receiver.full_name : ''
                    }
                    alt='' />
                </div>
              </div>

              < div className='absolute top-0 left-3'>
                <div className='shrink-0 w-8 h-8 relative'>
                  <UserAvatar
                    image={
                      sender.length > 0
                        ? sender
                          .filter((s: any) => s.user_id !== Number(host_guest_user_id))
                          .map((s: any) => s.image)
                          .join(', ')
                        : sender.user_id !== Number(host_guest_user_id) ? sender.image : ''
                    }
                    fullName={
                      sender.length > 0
                        ? sender
                          .filter((s: any) => s.user_id !== Number(host_guest_user_id))
                          .map((s: any) => s.full_name)
                          .join(', ')
                        : sender.user_id !== Number(host_guest_user_id) ? sender.full_name : ''
                    }
                    alt='' />
                </div>
              </div>
            </React.Fragment>
            :
            <div className='shrink-0 w-14 h-14 relative'>
              <UserAvatar
                image={
                  receiver.length > 0
                    ? receiver
                      .filter((r: any) => r.user_id !== Number(host_guest_user_id))
                      .map((r: any) => r.image)
                      .join(', ')
                    : receiver.user_id !== Number(host_guest_user_id) ? receiver.image : ''
                }
                fullName={
                  receiver.length > 0
                    ? receiver
                      .filter((r: any) => r.user_id !== Number(host_guest_user_id))
                      .map((r: any) => r.full_name)
                      .join(', ')
                    : receiver.user_id !== Number(host_guest_user_id) ? receiver.full_name : ''
                } alt='' />
            </div>
          }

        </div>

        <div className='flex-1 flex-col'>
          <div className='flex justify-between'>
            <p className={`text-xs ${STATUS_CLASSNAMES[status]}`}>{STATUS_DISPLAY_NAMES[status]}</p>
            <p className='text-sm text-gray-500'>{formattedDate}</p>
          </div>
          {to_user.length ?
            <p className={`${isRead ? 'text-gray-500' : 'font-bold text-gray-0'}`}>
              {/* {user?.user_id} */}
              {
                receiver.length
                  ? receiver
                    .filter(
                      (r: any) => {
                        console.log('receiver user id', r.user_id, Number(host_guest_user_id))
                        return r.user_id !== Number(host_guest_user_id)
                      })
                    .map((r: any) => r.full_name.split(' ')[0])
                    .join(', ')
                  : receiver.user_id !== Number(host_guest_user_id) ? receiver.full_name.split(' ')[0] : ''
              },
              {
                sender.length
                  ? sender
                    .filter(
                      (s: any) => {
                        console.log('sender user id', s.user_id, Number(host_guest_user_id))
                        console.log('sender user type', typeof s.user_id)
                        console.log('Number(host_guest_user_id) type', typeof Number(host_guest_user_id))
                        return s.user_id !== Number(host_guest_user_id)
                      })
                    .map((s: any) => s.full_name.split(' ')[0])
                    .join(', ')
                  : sender.user_id !== Number(host_guest_user_id) ? sender.full_name.split(' ')[0] : ''
              }
            </p>
            :
            <p className={`${isRead ? 'text-gray-500' : 'font-bold text-gray-0'}`}>
              {
                receiver.length
                  ? receiver
                    .filter(
                      (r: any) => {
                        console.log('receiver user id', r.user_id)
                        return r.user_id !== Number(host_guest_user_id)
                      })
                    .map((r: any) => r.full_name.split(' ')[0])
                    .join(', ')
                  : receiver.user_id !== Number(host_guest_user_id) ? receiver.full_name.split(' ')[0] : ''
              }
              {/* {
                sender.length
                  ? sender
                    .filter(
                      (s: any) => {
                        console.log('sender user id', s.user_id)
                        s.user_id !== user?.user_id
                      })
                    .map((s: any) => s.full_name.split(' ')[0])
                    .join(', ')
                  : sender.user_id !== user?.user_id ? sender.full_name.split(' ')[0] : ''
              } */}

            </p>}
          <div className='flex justify-between items-center gap-1 mt-1'>
            <p className={`ellipsis-one-line break-all ${isRead ? 'text-gray-500' : 'font-bold text-gray-0'}`}>
              {m_type === 'system' ? 'Stayverz: ' : user?.user_id !== sender.user_id ? 'You: ' : ''}

              {parsedData ?
                <div>
                  <span>{parsedData?.message}</span>
                  <span>{parsedData?.cost}</span>
                </div>
                :
                <span>
                  {content}
                </span>
              }
            </p>
            {isRead ? null : <ArrowBendUpLeft className='shrink-0' size={16} weight='bold' color='#6b7280' />}
          </div>
          <p className='text-sm text-gray-500 ellipsis-one-line break-all'>{duration} · {listing.name}</p>
        </div>
      </div>
    </Link >
  )
}


const STATUS_CLASSNAMES: Record<`${ConverstationStatus}`, string> = {
  inquiry: 'text-red-800',
  confirmed: 'text-green-800',
  cancelled: 'text-red-500',
}

const STATUS_DISPLAY_NAMES: Record<`${ConverstationStatus}`, string> = {
  inquiry: 'Inquiry',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
}
