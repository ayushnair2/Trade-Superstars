import { sportColor } from '../sportColors'

type Props = {
  sport: string
}

export default function SportTag({ sport }: Props) {
  const color = sportColor(sport)
  return (
    <span className="tag" style={{ color, borderColor: color }}>
      {sport}
    </span>
  )
}
