import { ArrowBendUpLeft } from '@phosphor-icons/react'
import Link from 'next/link'
import { FC, useMemo } from 'react'
import { DATE_FORMAT } from '~/app/chat/constants'
import { useSenderReceiver } from '~/app/chat/hooks/useSenderReceiver'
import { useChatSessionConversationMessages } from '~/app/chat/store/chatSessionStore'
import { UserAvatar } from '~/components/layout/UserAvatar'
import { formatDate, formatTime } from '~/lib/utils/formatter/dateFormatter'
import { ConverstationStatus, type Conversation as ConversationData } from '~/queries/models/conversation'


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

  console.log('receiver', receiver)
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
        {receiver.length > 0 ?
          <div className='relative w-10 h-10 mr-5'>
            <div className='absolute top-3 left-0'>
              <div className='shrink-0 w-8 h-8 relative'>
                <UserAvatar image={receiver.length > 0 ? receiver[0]?.image : receiver?.image} fullName={receiver.length > 0 ? receiver[0]?.full_name : receiver?.full_name} alt='' />
              </div>
            </div>
            <div  className='absolute top-0 left-3'>
              <div className='shrink-0 w-8 h-8 relative'>
                <UserAvatar image={receiver.length > 0 ? receiver[1]?.image : receiver?.image} fullName={receiver.length > 0 ? receiver[1]?.full_name : receiver?.full_name} alt='' />
              </div>
            </div>
          </div>
          :
          <div className='shrink-0 w-14 h-14 relative'>
            <UserAvatar image={receiver.length > 0 ? receiver[1]?.image : receiver?.image} fullName={receiver.length > 0 ? receiver[1]?.full_name : receiver?.full_name} alt='' />
          </div>
        }
        <div className='flex-1 flex-col'>
          <div className='flex justify-between'>
            <p className={`text-xs ${STATUS_CLASSNAMES[status]}`}>{STATUS_DISPLAY_NAMES[status]}</p>
            <p className='text-sm text-gray-500'>{formattedDate}</p>
          </div>
          <p className={`${isRead ? 'text-gray-500' : 'font-bold text-gray-0'}`}>{receiver.length > 0 ? receiver[0].full_name.split(' ')[0] + ', ' + receiver[1].full_name.split(' ')[0] : receiver.full_name}</p>
          <div className='flex justify-between items-center gap-1 mt-1'>
            <p className={`ellipsis-one-line break-all ${isRead ? 'text-gray-500' : 'font-bold text-gray-0'}`}>
              {m_type === 'system' ? 'Stayverz: ' : user?.user_id === sender.user_id ? 'You: ' : ''}

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
    </Link>
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
