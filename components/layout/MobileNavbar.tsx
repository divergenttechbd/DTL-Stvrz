import { HouseLine } from '@phosphor-icons/react'
import { CalendarBlank } from '@phosphor-icons/react/dist/ssr/CalendarBlank'
import { CalendarCheck } from '@phosphor-icons/react/dist/ssr/CalendarCheck'
import { ChatText } from '@phosphor-icons/react/dist/ssr/ChatText'
import { HandCoins } from '@phosphor-icons/react/dist/ssr/HandCoins'
import { House } from '@phosphor-icons/react/dist/ssr/House'
import { List } from '@phosphor-icons/react/dist/ssr/List'
import { MagnifyingGlass } from '@phosphor-icons/react/dist/ssr/MagnifyingGlass'
import { UserCircle } from '@phosphor-icons/react/dist/ssr/UserCircle'
import { usePathname, useRouter } from 'next/navigation'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { getToken } from '~/lib/storage/token'
import { updateUnreadMessageCount, useAuthStore } from '~/store/authStore'
import { styles } from '~/styles/classes'

export interface NavigationItem {
  key: string
  label: string
  icon: (color: string, size: number) => React.ReactNode
  render?: () => React.ReactNode
  pathName?: string
  notification?: number
  action?: () => void
}

const MobileNavbar = () => {
  const router = useRouter()
  const { isAuthenticated, userData } = useAuthStore()
  const { u_type: user_type } = userData || {}
  const [messageCount, setMessageCount] = useState(
    userData?.unread_message_count
  )
  const token = getToken()
  console.log('unread message count -', userData?.unread_message_count)
  // set message count
  useEffect(() => {
    if(userData) {
      console.log('got user data -', userData?.unread_message_count)
      setMessageCount(userData?.unread_message_count)
    }
  }, [userData])
  useEffect(() => {
    let ws = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/chat-stat/?token=${token}`) //API Host Message Inbox Count
    ws.onmessage = (ev: MessageEvent<any>) => {
      const data = JSON.parse(ev.data)
      setMessageCount(data?.count)
      updateUnreadMessageCount(data?.count)
      console.log('got message count -', data?.count)
    }
  }, [])

  const currentPath = usePathname()

  const handleRouting = useCallback((pathName: string) => {
    if (isAuthenticated || pathName === '/' || pathName === '/room-list') {
      router.push(pathName)
    } else {
      useAuthStore.setState({ authFlow: 'LOG_IN' })
    }
  }, [isAuthenticated, router])

  const handleMenuClick = useCallback((menuItem: NavigationItem) => {
    return () => {
      if (menuItem.action) {
        menuItem.action()
      } else {
        handleRouting(menuItem.pathName || '/')
      }
    }
  }, [handleRouting])



  const menus: NavigationItem[] = useMemo(() => {
    return (user_type === 'guest' || !isAuthenticated) ? [
      {
        key: 'EXPLORE',
        label: 'Explore',
        icon: (color: string, size: number) => <MagnifyingGlass size={size} color={color} />,
        pathName: '/',
      },
      {
        key: 'LISTING',
        label: 'Listings',
        icon: (color: string, size: number) => <HouseLine size={size} color={color} />,
        pathName: '/room-list',
      },
      {
        key: 'TRIPS',
        label: 'Trips',
        icon: (color: string, size: number) => <CalendarCheck size={size} color={color} />,
        pathName: '/trips',
      },
      {
        key: 'MESSAGES',
        label: 'Inbox',
        icon: (color: string, size: number) => <ChatText size={size} color={color} />,
        pathName: '/messages',
        notification: messageCount,
      },
      {
        key: 'PROFILE/LOGIN',
        label: isAuthenticated ? 'Profile' : 'Log In',
        icon: (color: string, size: number) => <UserCircle size={size} color={color} />,
        pathName: '/account-settings',
        // action: () => handleRouting('/host-dashboard/inbox')
      },
    ] :
      [
        {
          key: 'TODAY',
          label: 'Today',
          icon: (color: string, size: number) => <House size={size} color={color} />,
          pathName: '/host-dashboard',
          // action: () => handleRouting('/host-dashboard')
        },
        {
          key: 'INBOX',
          label: `Inbox`,
          icon: (color: string, size: number) => <ChatText size={size} color={color} />,
          pathName: '/host-dashboard/inbox',
          notification: messageCount,
        },
        {
          key: 'CALENDAR',
          label: 'Calendar',
          icon: (color: string, size: number) => <CalendarBlank size={size} color={color} />,
          pathName: '/host-dashboard/calendar-listings',
        },
        {
          key: 'EARNINGS',
          label: 'Earnings',
          icon: (color: string, size: number) => <HandCoins size={size} color={color} />,
          pathName: '/host-dashboard/earnings',
        },
        {
          key: 'MENU',
          label: 'Menu',
          icon: (color: string, size: number) => <List size={size} color={color} />,
          pathName: '/host-dashboard/menu',
        },

      ]
  }, [isAuthenticated, messageCount, user_type])

  return (
    <div className='fixed bottom-0 left-0 right-0 mx-auto w-full bg-white px-0 py-2 border-t shadow z-50'>
      <div className=' w-full h-full'>
        <ul className='flex w-full justify-between items-center'>
          {menus.map((el) => (
            <li key={el.key} className={`${styles.flexCenter} flex-1`}>
              <button onClick={handleMenuClick(el)} className='flex flex-col gap-1 items-center justify-center relative'>
                {!!el?.notification && (
                  <div className='absolute -top-1 -right-1 flex justify-center items-center bg-[#f66c0e] w-4 h-4 rounded-full text-[#ffffff] text-[0.45rem]'>{el.notification}</div>
                )}
                <div className=''>
                  {el.icon(`${currentPath === el.pathName ? '#f66c0e' : 'rgba(113,113,113,1)'}`, 25)}
                </div>
                <div className={`text-[10px] font-medium  ${currentPath === el.pathName ? 'text-[#f66c0e]' : 'text-[#616161]'}`}>
                  {el.label}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default MobileNavbar
