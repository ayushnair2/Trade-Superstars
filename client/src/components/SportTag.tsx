type Props = {
  sport: string
}

// The mockup tags NBA in cyan and other leagues in amber.
export default function SportTag({ sport }: Props) {
  const className = sport === 'NBA' ? 'tag' : 'tag tag-alt'
  return <span className={className}>{sport}</span>
}
