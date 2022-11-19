export default function showResults(drawResultArr, person) {  
  if (!drawResultArr)  {
    console.warn('Start lottery first')
    return
  }
  const result = drawResultArr.find(
    res => {
      return Object.keys(res).toString() === person
    }
  );
  
  const personPicked = Object.values(result).toString();
  
  return personPicked;
}