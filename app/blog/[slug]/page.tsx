'use client'

import { useQuery } from '@tanstack/react-query'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { FC } from 'react'
import Loader from '~/components/loader/Loader'
import { getBlogDetails } from '~/queries/client/blog'

const BlogDetails: FC = () => {
  const pathname = usePathname()
  const pathArr = pathname.split('/')
  const slug = pathArr[pathArr.length-1]

  const { isLoading, data:blogDetails, error } = useQuery<any>({
    queryKey: ['blogDetails', slug],
    queryFn: () => getBlogDetails(slug as any),
    enabled: !!slug
  })

  if (isLoading) return <Loader />
  if (error) return <p>An error occurred: {(error as Error).message}</p>


  const date = new Date(blogDetails?.data?.created_at)
  const formattedDate = new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'long',
    day: '2-digit'
  }).format(date)

  return (
    <div className='container mx-auto mt-5 lg:mt-0 mb-10 pt-navbar'>

      <article>
        <h1 className='text-3xl font-bold text-center mb-5'>{blogDetails?.data?.title}</h1>
        <p className='text-base text-grayText mb-10 text-center'>{formattedDate}</p>
        <div className='relative h-[500px] w-full mb-20'>
          <Image
            src={blogDetails?.data?.image}
            alt={blogDetails?.data?.title}
            className='rounded-t-lg w-full object-cover'
            layout='fill'
            objectFit='cover'
          />
        </div>
        {
          blogDetails?.data?.description && (
            <div dangerouslySetInnerHTML={{ __html: blogDetails?.data?.description }}/>
          )
        }
      </article>
    </div>
  )
}

export default BlogDetails
