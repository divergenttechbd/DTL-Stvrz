import React, { FC, useCallback, useMemo, useState } from 'react'
// import Image from 'next/image'
import { UserAvatar } from '~/components/layout/UserAvatar'
import { formatTime } from '~/lib/utils/formatter/dateFormatter'
// import GuestHouseLogo from '~/public/nav-brand-logo.svg'
import { DATE_FORMAT } from '~/app/chat/constants'
import { useConversationDetailsActions } from '~/app/chat/store/conversationDetailsStore'
import { formatDate } from '~/lib/utils/formatter/dateFormatter'
import { Peer, type Message as MessageData } from '~/queries/models/conversation'
// import { DotsThree } from '@phosphor-icons/react'
import { ArrowCounterClockwise } from '@phosphor-icons/react'
import { useRouter } from 'next/navigation'

export interface MessageProps {
  index: number
  messages: MessageData[]
  receiver?: Peer
  onRetrySend: () => void
  onReport: (id: string) => void
}

export const Message: FC<MessageProps> = ({
  index,
  messages,
  receiver,
  onRetrySend,
  onReport,
}) => {
  const { content, user, created_at, m_type, meta, id, is_read, is_failed } = messages[index]

  const router = useRouter()

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

  const previousMessage = messages[index - 1]
  const nextMessage = messages[index + 1]
  const isContinuingMessage = (previousMessage?.m_type === m_type) && ((previousMessage?.user.username === user.username) && (formatTime(previousMessage?.created_at) === formatTime(created_at)))
  const willContinueMessage = (nextMessage?.m_type === m_type) && ((nextMessage?.user.username === user.username) && (formatTime(nextMessage?.created_at) === formatTime(created_at)))
  const isContinuingDate = useMemo(() => (formatDate(previousMessage?.created_at) === formatDate(created_at)), [previousMessage, created_at])
  const { setActiveMessageMeta } = useConversationDetailsActions()
  const isSeen = (index === (messages.length - 1)) && (user.id !== receiver?.id) && is_read && !willContinueMessage
  const [isRetrying, setIsRetrying] = useState(false)


  const handleClickMeta = useCallback((meta: Required<MessageData['meta']>) => () => {
    setActiveMessageMeta(meta)
  }, [setActiveMessageMeta])

  // const handleReport = useCallback(() => {
  //   if (id) onReport(id)
  // }, [onReport, id])

  const handleRetrySend = useCallback(() => {
    if(isRetrying || !id) return
    setIsRetrying(true)
    onRetrySend()
    setIsRetrying(false)
  }, [id, isRetrying, onRetrySend])


  return (
    <div className={`flex flex-col ${!isContinuingMessage ? 'sm:pt-5 pt-3' : 'py-1'}`}>
      {!isContinuingDate ? <h4 className='max-sm:text-xs text-sm text-gray-600 text-center font-medium py-5'>
        {formatDate(created_at, DATE_FORMAT)}
      </h4> : null}
      {m_type === 'system' ?
        <div className='flex shrink-0 sm:gap-4 gap-2 items-center rounded-full bg-gray-100 p-3 px-4 w-full mb-2'>
          {/* <Image src={GuestHouseLogo} width={20} height={20} alt='bdbnb icon' /> */}
          <p className='font-medium max-sm:text-xs text-sm mb-0 text-gray-600 break-words'>
            {content} {' '}
            {meta ? <span className='underline cursor-pointer whitespace-nowrap' onClick={handleClickMeta(meta)}>Show details</span> : null}
          </p>
        </div>
        : <div className={'flex gap-4'}>
          <div className={`shrink-0 w-10 ${isContinuingMessage ? 'h-0' : 'h-10'} relative`}>
            {!isContinuingMessage ? <UserAvatar image={user.image} fullName={user.full_name} alt='' size='sm' /> : null}
          </div>
          <div className='flex flex-col w-[calc(100%-2.5rem)]'>
            {!isContinuingMessage ? <div className='flex flex-wrap gap-2 items-center mb-1'>
              <h4 className='font-medium'>{user.full_name}</h4>
              <p className='text-gray-500 text-xs sm:text-sm leading-none'>{formatTime(created_at)}</p>
            </div> : null}
            <div className='group flex items-center justify-between w-full relative'>
              <React.Fragment>
                {parsedData ?
                  <div className='w-fit shadow-[0px_1px_4px_0px_rgba(0,0,0,0.25)] rounded-lg py-3 px-3'>
                    <div className='relative flex items-center gap-3 justify-between '>
                      <div className='h-24 w-32'>
                        <picture>
                          <img src={parsedData?.image} className='w-full h-full object-cover rounded-md' alt='property-image' />
                        </picture>
                      </div>
                      <div className='h-16 border-2 border-[#F15925] rounded-full'></div>
                      <div className='space-y-1 text-sm'>
                        <p className='font-semibold pe-4'>{parsedData?.message}</p>
                        <p>Price: {parsedData?.cost}</p>
                      </div>
                      <div onClick={() => {
                        window.open(`https://stayverz.divergenttechbd.com/rooms/${parsedData?.property_id}`,'_blank')
                      }} className='absolute text-sm text-[#F15925] font-semibold cursor-pointer -right-1.5 -bottom-1.5'>View Details</div>
                    </div>
                  </div>
                  :
                  <p className={`grow font-base break-words whitespace-pre-wrap w-[calc(100%-5rem)] ${is_failed ? 'text-[#777777]' : 'text-[#202020]'} ${isContinuingMessage ? '' : 'py-1'}`}>{content}</p>

                }
              </React.Fragment>

              {is_failed ? <span title='Retry'> <ArrowCounterClockwise width={20} height={20} weight='bold' color='#444444' className={`cursor-pointer ${isRetrying ? 'animate-reverse-spin' : ''}`} onClick={handleRetrySend} /></span> : null}
              {/* <div className='cursor-pointer rounded-full group-hover:bg-white w-6 h-6 flex items-center justify-center hover:border hover:border-slate-300 absolute right-1' onClick={handleReport}>
                <DotsThree size={22} color='#222222' weight='bold' className='shrink-0 mx-2 hidden group-hover:block' />
              </div> */}
            </div>
            {(isSeen && receiver?.full_name) ? <p className='text-[.70rem] text-gray-500 mt-[.15rem] leading-none' title={`Seen by ${receiver.full_name}`}>Message seen</p> : null}
          </div>
        </div>
      }
    </div>
  )
}

