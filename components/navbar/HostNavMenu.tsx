import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { FC, useEffect, useMemo, useState } from 'react'
import Dropdown from '~/components/layout/Dropdown'
import MenuDropdownToggler from '~/components/navbar/MenuDropdownToggler'
import { getToken } from '~/lib/storage/token'
import { useAuthStore } from '~/store/authStore'

const HostNavMenu:FC = () => {
  const { userData ,isAuthenticated} = useAuthStore()
  const { u_type: user_type } = userData || {}
  const [messageCount, setMessageCount] = useState(
    userData?.unread_message_count
  )
  const token = getToken()
  // set message count
  useEffect(() => {
    if(userData){
      setMessageCount(userData?.unread_message_count)
    }
  }, [userData])
  useEffect(() => {
    let ws = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/chat-stat/?token=${token}`) //API Host Message Inbox Count
    ws.onmessage = (ev: MessageEvent<any>) => {
      const data = JSON.parse(ev.data)
      setMessageCount(data?.count)
    }
  }, [])

  const pathname = usePathname()

  const navMenus = useMemo(() => {
    return (user_type === 'guest' || !isAuthenticated) ? [
      { key: 'HOME', label: 'Home', path: '/' },
      { key: 'LISTING', label: 'Listing', path: '/room-list' },
      { key: 'BLOGS', label: 'Blog', path: '/blog' },
      { key: 'ABOUT', label: 'About', path: '/aboutus' },
      { key: 'CONTACT', label: 'Contact', path: '/contact' }
    ] : [
      { key: 'TODAY', label: 'Today', path: '/host-dashboard' },
      { key: 'INBOX', label: 'Inbox', path: '/host-dashboard/inbox', notification: messageCount },
      { key: 'CALENDAR', label: 'Calendar', path: '/host-dashboard/calendar' },
      { key: 'EARNINGS', label: 'Earnings', path: '/host-dashboard/earnings' },
      { key: 'MENU', label: 'Menu', path: '' }
    ]
  }, [isAuthenticated, messageCount, user_type])
  const dropdownMenus = useMemo(() => {
    return [
      { key: 'LISTING', label: 'Listings', path: '/host-dashboard/listing'},
      { key: 'RESERVATIONS', label: 'Reservations', path: '/host-dashboard/reservations'},
      { key: 'PAYOUT', label: 'Payouts', path: '/host-dashboard/payouts' },
      { key: 'BLOGS', label: 'Blogs', path: '/blog' },
      { key: 'ABOUT', label: 'About us', path: '/aboutus' },
      { key: 'CONTACT', label: 'Contact', path: '/contact' }
    ]
  }, [])


  return (
    <>
      {navMenus?.map((item) => (
        (item.key === 'MENU') ? 
          <Dropdown 
            key={item.key}
            menus={dropdownMenus} 
            renderToggler={({toggle, isShown}) => <MenuDropdownToggler onToggle={toggle} isShown={isShown}/>}
          /> : 
          <Link
            href={item.path || '#'}
            key={item.key}
            className={`text-sm flex items-center gap-1 text-grayText font-semibold relative px-4 py-[10px] hover:bg-grayBg rounded-[42px] ${pathname === item.path ? 'before:absolute before:bg-[#f66c0e] before:border-b-3  before:content-[""] before:h-[2px] before:w-4 before:bottom-0 before:left-1/2 before:-translate-x-1/2' : ''}`}
          >
            {item.label}
            {!!item.notification && (
              <div className='absolute top-0 right-0 flex justify-center items-center bg-[#f66c0e] w-4 h-4 rounded-full text-[#ffffff] text-[0.45rem]'>{item.notification}</div>
            )}
          </Link>
      ))}
    </>
  )
}

export default HostNavMenu
